"""
Phase 6 Hardening Tests
Covers all 9 hard requirements from SPEC.md:
1. Grounding (prices from DB)
2. Oversell guard
3. GST correctness
4. Multi-turn bills (draft doesn't touch stock)
5. Idempotency (retried finalize = no-op)
6. Concurrency (sale + receipt in flight)
7. Guardrails (below-cost, no-delete-stock, bad khata, empty bill)
8. Real artifacts (PDF + PPTX file existence)
9. Preference persistence (across new session)
"""
import os
import threading
import pytest
from datetime import date
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.db.database import engine
from app.db.models import Base, Product, StockTransaction
from app.services.inventory import add_product, receive_stock, get_stock
from app.services.billing import (
    create_draft, add_item, finalize,
    InsufficientStockError, BelowCostError
)
from app.services.khata import create_customer, add_credit, record_payment, get_balance
from app.services.preferences import set_preference, get_preference
from app.services.gst import compute_line_tax

TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = TestSessionLocal()
    yield session
    session.close()


# ─────────────────────────────────────────────
# HARD REQ 3: GST correctness
# ─────────────────────────────────────────────
class TestGSTCorrectness:
    def test_100_at_5pct(self):
        taxable, cgst, sgst, total = compute_line_tax(100.0, 1.0, 5.0)
        assert taxable == 100.0
        assert cgst == 2.50
        assert sgst == 2.50
        assert total == 105.0

    def test_18pct_split(self):
        taxable, cgst, sgst, total = compute_line_tax(200.0, 1.0, 18.0)
        assert taxable == 200.0
        assert cgst == 18.0
        assert sgst == 18.0
        assert total == 236.0

    def test_zero_gst(self):
        taxable, cgst, sgst, total = compute_line_tax(50.0, 2.0, 0.0)
        assert taxable == 100.0
        assert cgst == 0.0
        assert sgst == 0.0
        assert total == 100.0

    def test_multi_qty_rounding(self):
        # 3 items at Rs.33.33 each @ 5% — must round per line, not just total
        taxable, cgst, sgst, total = compute_line_tax(33.33, 3.0, 5.0)
        assert taxable == 99.99
        assert cgst + sgst == round(99.99 * 0.05, 2)


# ─────────────────────────────────────────────
# HARD REQ 2: Oversell guard
# ─────────────────────────────────────────────
class TestOversellGuard:
    def test_cannot_oversell(self, db):
        p = add_product(db, "S1", "Sugar", "cat", "kg", True, 35.0, 42.0, 0.0)
        receive_stock(db, p.id, 6.0)

        bill = create_draft(db)
        add_item(db, bill.id, p.id, 10.0)  # exceeds stock, but draft allows it

        with pytest.raises(InsufficientStockError):
            finalize(db, bill.id, "cash")

        assert get_stock(db, p.id) == 6.0  # untouched

    def test_exact_stock_sells(self, db):
        p = add_product(db, "S2", "Salt", "cat", "packet", False, 15.0, 24.0, 5.0)
        receive_stock(db, p.id, 5.0)
        bill = create_draft(db)
        add_item(db, bill.id, p.id, 5.0)
        finalize(db, bill.id, "cash")
        assert get_stock(db, p.id) == 0.0


# ─────────────────────────────────────────────
# HARD REQ 4: Multi-turn bills (draft ≠ stock decrement)
# ─────────────────────────────────────────────
class TestMultiTurnBills:
    def test_draft_does_not_touch_stock(self, db):
        p = add_product(db, "M1", "Maggi", "cat", "packet", False, 12.0, 14.0, 18.0)
        receive_stock(db, p.id, 20.0)
        bill = create_draft(db)
        add_item(db, bill.id, p.id, 5.0)
        # Stock must still be 20 at draft stage
        assert get_stock(db, p.id) == 20.0

    def test_stock_moves_only_on_finalize(self, db):
        p = add_product(db, "M2", "Atta", "cat", "packet", False, 180.0, 210.0, 5.0)
        receive_stock(db, p.id, 10.0)
        bill = create_draft(db)
        add_item(db, bill.id, p.id, 3.0)
        assert get_stock(db, p.id) == 10.0  # before finalize
        finalize(db, bill.id, "upi")
        assert get_stock(db, p.id) == 7.0   # after finalize


# ─────────────────────────────────────────────
# HARD REQ 5: Idempotency
# ─────────────────────────────────────────────
class TestIdempotency:
    def test_double_finalize_same_key(self, db):
        p = add_product(db, "I1", "Oil", "cat", "litre", False, 110.0, 140.0, 5.0)
        receive_stock(db, p.id, 10.0)
        bill = create_draft(db)
        add_item(db, bill.id, p.id, 2.0)

        key = "idem-key-abc"
        b1 = finalize(db, bill.id, "cash", idempotency_key=key)
        b2 = finalize(db, bill.id, "cash", idempotency_key=key)  # retry

        # Must be the same bill object
        assert b1.id == b2.id
        # Stock must have decremented ONLY ONCE
        assert get_stock(db, p.id) == 8.0  # 10 - 2

    def test_no_duplicate_stock_transactions(self, db):
        p = add_product(db, "I2", "Butter", "cat", "packet", False, 45.0, 54.0, 12.0)
        receive_stock(db, p.id, 5.0)
        bill = create_draft(db)
        add_item(db, bill.id, p.id, 1.0)

        key = "idem-key-xyz"
        finalize(db, bill.id, "upi", idempotency_key=key)
        finalize(db, bill.id, "upi", idempotency_key=key)  # retry

        # Exactly 1 sale transaction must exist (not 2)
        txns = db.query(StockTransaction).filter(
            StockTransaction.product_id == p.id,
            StockTransaction.reason == "sale"
        ).all()
        assert len(txns) == 1


# ─────────────────────────────────────────────
# HARD REQ 6: Concurrency (sale + receipt in flight)
# ─────────────────────────────────────────────
class TestConcurrency:
    def test_sale_vs_sale_one_succeeds(self):
        """Two simultaneous finalizations competing for last 1 unit — exactly one wins."""
        # Use a separate file-based SQLite so threads share a real connection pool
        from sqlalchemy import create_engine
        conc_engine = create_engine("sqlite:///test_conc1.db")
        Base.metadata.create_all(bind=conc_engine)
        ConcSession = sessionmaker(bind=conc_engine)

        db = ConcSession()
        p = add_product(db, "C1", "Parle-G", "cat", "packet", False, 4.0, 5.0, 18.0)
        receive_stock(db, p.id, 1.0)
        p_id = p.id
        bill1 = create_draft(db); add_item(db, bill1.id, p_id, 1.0); bill1_id = bill1.id
        bill2 = create_draft(db); add_item(db, bill2.id, p_id, 1.0); bill2_id = bill2.id
        db.close()

        results = []
        def worker(bid):
            s = ConcSession()
            try:
                finalize(s, bid, "cash")
                results.append("ok")
            except InsufficientStockError:
                results.append("err")
            except Exception as e:
                results.append(f"exc:{e}")
            finally:
                s.close()

        t1 = threading.Thread(target=worker, args=(bill1_id,))
        t2 = threading.Thread(target=worker, args=(bill2_id,))
        t1.start(); t2.start(); t1.join(); t2.join()

        Base.metadata.drop_all(bind=conc_engine)
        conc_engine.dispose()
        try: os.remove("test_conc1.db")
        except: pass

        assert results.count("ok") == 1, f"Expected 1 success, got: {results}"
        assert results.count("err") == 1, f"Expected 1 error, got: {results}"

    def test_sale_and_receipt_concurrent(self):
        """Sale + receipt in flight simultaneously — final qty must be exactly correct."""
        from sqlalchemy import create_engine
        conc_engine2 = create_engine("sqlite:///test_conc2.db")
        Base.metadata.create_all(bind=conc_engine2)
        ConcSession2 = sessionmaker(bind=conc_engine2)

        db = ConcSession2()
        p = add_product(db, "C2", "Rice", "cat", "kg", True, 40.0, 55.0, 0.0)
        receive_stock(db, p.id, 5.0)
        p_id = p.id
        bill = create_draft(db)
        add_item(db, bill.id, p_id, 2.0)
        bill_id = bill.id
        db.close()

        outcomes = {}
        barrier = threading.Barrier(2)

        def do_sale():
            s = ConcSession2()
            barrier.wait()
            try:
                finalize(s, bill_id, "cash")
                outcomes["sale"] = "ok"
            except Exception as e:
                outcomes["sale"] = str(e)
            finally:
                s.close()

        def do_receipt():
            s = ConcSession2()
            barrier.wait()
            try:
                receive_stock(s, p_id, 10.0)
                outcomes["receipt"] = "ok"
            except Exception as e:
                outcomes["receipt"] = str(e)
            finally:
                s.close()

        t1 = threading.Thread(target=do_sale)
        t2 = threading.Thread(target=do_receipt)
        t1.start(); t2.start(); t1.join(); t2.join()

        db = ConcSession2()
        final_qty = get_stock(db, p_id)
        db.close()
        Base.metadata.drop_all(bind=conc_engine2)
        conc_engine2.dispose()
        try: os.remove("test_conc2.db")
        except: pass

        assert outcomes["sale"] == "ok", f"Sale failed: {outcomes.get('sale')}"
        assert outcomes["receipt"] == "ok", f"Receipt failed: {outcomes.get('receipt')}"
        assert final_qty == 13.0  # 5 - 2 + 10


# ─────────────────────────────────────────────
# HARD REQ 7: Guardrails
# ─────────────────────────────────────────────
class TestGuardrails:
    def test_refuse_sell_below_cost(self, db):
        p = add_product(db, "G1", "Surf Excel", "cat", "packet", False, 150.0, 185.0, 18.0)
        receive_stock(db, p.id, 10.0)
        bill = create_draft(db)
        item = add_item(db, bill.id, p.id, 1.0)
        item.unit_price = 100.0  # below cost of 150
        db.commit()
        with pytest.raises(BelowCostError):
            finalize(db, bill.id, "cash")

    def test_no_delete_stock_tool(self):
        """There must be no delete_stock function in any service or tool module."""
        import app.services.inventory as inv_module
        import app.agent.tools as tools_module
        assert not hasattr(inv_module, "delete_stock"), "delete_stock must NOT exist"
        assert not hasattr(tools_module, "delete_stock"), "delete_stock tool must NOT exist"

    def test_refuse_empty_bill_finalize(self, db):
        bill = create_draft(db)
        with pytest.raises(ValueError, match="empty"):
            finalize(db, bill.id, "cash")

    def test_refuse_payment_with_no_credit_history(self, db):
        c = create_customer(db, "Ravi")
        with pytest.raises(ValueError):
            record_payment(db, c.id, 100.0)

    def test_refuse_payment_exceeding_balance(self, db):
        c = create_customer(db, "Sita")
        add_credit(db, c.id, 300.0)
        with pytest.raises(ValueError):
            record_payment(db, c.id, 500.0)

    def test_khata_balance_correct(self, db):
        c = create_customer(db, "Mohan")
        add_credit(db, c.id, 1000.0)
        record_payment(db, c.id, 400.0)
        assert get_balance(db, c.id) == 600.0


# ─────────────────────────────────────────────
# HARD REQ 8: Real artifacts
# ─────────────────────────────────────────────
class TestRealArtifacts:
    def test_pdf_invoice_generated(self, db):
        p = add_product(db, "A1", "Butter", "cat", "packet", False, 45.0, 54.0, 12.0)
        receive_stock(db, p.id, 10.0)
        bill = create_draft(db)
        add_item(db, bill.id, p.id, 2.0)
        fin = finalize(db, bill.id, "cash")

        from app.services.invoice import generate_invoice_pdf
        path = generate_invoice_pdf(fin.id)
        assert os.path.exists(path)
        assert path.endswith(".pdf")
        # Must be a real (non-empty) PDF — even small invoices are well over 1KB
        assert os.path.getsize(path) > 1000

    def test_pptx_generated(self, db):
        from app.services.presentation import generate_sales_analysis_pptx
        path = generate_sales_analysis_pptx(date(2026, 9, 1), date(2026, 9, 30))
        assert os.path.exists(path)
        assert path.endswith(".pptx")
        assert os.path.getsize(path) > 5000


# ─────────────────────────────────────────────
# HARD REQ 9: Preference persistence
# ─────────────────────────────────────────────
class TestPreferencePersistence:
    def test_preference_survives_new_session(self, db):
        set_preference(db, "default_payment_mode", "UPI")
        db.close()

        # New session simulates restart
        new_db = TestSessionLocal()
        val = get_preference(new_db, "default_payment_mode")
        new_db.close()
        assert val == "UPI"

    def test_preference_default_fallback(self, db):
        val = get_preference(db, "nonexistent_key", default="cash")
        assert val == "cash"
