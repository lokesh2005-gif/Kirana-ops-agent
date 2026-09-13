import os
import pytest
import threading
from app.db.database import engine
from app.db.models import Base, Product, Customer
from sqlalchemy.orm import sessionmaker

from app.services.gst import compute_line_tax
from app.services.inventory import add_product, receive_stock, get_stock
from app.services.billing import create_draft, add_item, finalize, InsufficientStockError, BelowCostError
from app.services.khata import create_customer, add_credit, record_payment, get_balance

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

def test_gst_computation():
    # 100 at 5% -> CGST=2.50, SGST=2.50, total=105
    taxable, cgst, sgst, total = compute_line_tax(100.0, 1.0, 5.0)
    assert taxable == 100.0
    assert cgst == 2.50
    assert sgst == 2.50
    assert total == 105.0

def test_billing_normal_and_oversell(db_session):
    p = add_product(db_session, "SKU1", "Item 1", "cat", "kg", False, 10.0, 20.0, 5.0)
    receive_stock(db_session, p.id, 6.0)
    
    bill = create_draft(db_session)
    # Draft should not touch stock
    add_item(db_session, bill.id, p.id, 2.0)
    assert get_stock(db_session, p.id) == 6.0
    
    finalize(db_session, bill.id, "cash", None, "key1")
    assert get_stock(db_session, p.id) == 4.0
    
    # Oversell test
    bill2 = create_draft(db_session)
    add_item(db_session, bill2.id, p.id, 10.0)
    
    with pytest.raises(InsufficientStockError):
        finalize(db_session, bill2.id, "cash")
        
    assert get_stock(db_session, p.id) == 4.0 # Stock unaffected

def test_sell_below_cost(db_session):
    p = add_product(db_session, "SKU2", "Item 2", "cat", "kg", False, 50.0, 60.0, 5.0)
    receive_stock(db_session, p.id, 10.0)
    
    bill = create_draft(db_session)
    item = add_item(db_session, bill.id, p.id, 1.0)
    
    # Manually hack unit price below cost
    item.unit_price = 40.0
    db_session.commit()
    
    with pytest.raises(BelowCostError):
        finalize(db_session, bill.id, "cash")

def test_idempotent_finalize(db_session):
    p = add_product(db_session, "SKU3", "Item 3", "cat", "kg", False, 10.0, 20.0, 5.0)
    receive_stock(db_session, p.id, 5.0)
    
    bill = create_draft(db_session)
    add_item(db_session, bill.id, p.id, 1.0)
    
    b1 = finalize(db_session, bill.id, "cash", None, "idemp-key-1")
    assert get_stock(db_session, p.id) == 4.0
    
    # finalize again with same key
    b2 = finalize(db_session, bill.id, "cash", None, "idemp-key-1")
    assert b1.id == b2.id
    assert get_stock(db_session, p.id) == 4.0 # Stock decrements only once

def test_khata_operations(db_session):
    c = create_customer(db_session, "Ram")
    
    # Reject payment when no balance
    with pytest.raises(ValueError):
        record_payment(db_session, c.id, 100.0)
        
    add_credit(db_session, c.id, 500.0)
    assert get_balance(db_session, c.id) == 500.0
    
    # Reject over-payment
    with pytest.raises(ValueError):
        record_payment(db_session, c.id, 600.0)
        
    record_payment(db_session, c.id, 200.0)
    assert get_balance(db_session, c.id) == 300.0

def test_concurrency_oversell():
    # Setup fresh DB specifically for concurrency
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    
    p = add_product(db, "SKU-CONC", "Conc", "cat", "kg", False, 10.0, 20.0, 5.0)
    receive_stock(db, p.id, 1.0)
    p_id = p.id
    
    bill1 = create_draft(db)
    add_item(db, bill1.id, p_id, 1.0)
    
    bill1_id = bill1.id
    
    bill2 = create_draft(db)
    add_item(db, bill2.id, p_id, 1.0)
    bill2_id = bill2.id
    
    db.close()
    
    results = []
    
    def worker(bill_id):
        session = TestingSessionLocal()
        try:
            finalize(session, bill_id, "cash")
            results.append("success")
        except InsufficientStockError:
            results.append("error")
        except Exception as e:
            results.append(str(e))
        finally:
            session.close()

    t1 = threading.Thread(target=worker, args=(bill1_id,))
    t2 = threading.Thread(target=worker, args=(bill2_id,))
    
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    assert results.count("success") == 1
    assert results.count("error") == 1
    
    # check final stock
    db = TestingSessionLocal()
    assert get_stock(db, p_id) == 0.0
    db.close()
    Base.metadata.drop_all(bind=engine)
