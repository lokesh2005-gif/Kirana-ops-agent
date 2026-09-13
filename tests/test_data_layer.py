import os
import pytest
from app.db.database import engine
from app.db.models import Base, Product
from app.db.seed import seed_db
from sqlalchemy.orm import sessionmaker

# Setup test DB (use memory for tests so we don't pollute local sqlite)
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

@pytest.fixture(scope="module")
def db_session():
    # Use the test engine
    test_engine = engine
    Base.metadata.create_all(bind=test_engine)
    
    # Run seed using the test engine implicitly through the seed_db which uses the imported engine.
    # To be safe, let's just make sure seed_db can work with test setup. 
    # Actually, seed.py uses app.db.database.engine which might be initialized before os.environ override.
    # Let's re-bind engine or override the seed_db behavior, but simpler: let seed_db run on the module engine.
    seed_db()
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=test_engine)

def test_seeded_data_validity(db_session):
    products = db_session.query(Product).all()
    assert len(products) > 0
    
    valid_units = {"kg", "g", "l", "ml", "packet", "dozen", "piece", "litre"}
    valid_gst = {0.0, 5.0, 12.0, 18.0}
    
    for p in products:
        # Check unit
        assert p.unit in valid_units, f"Invalid unit {p.unit} for {p.name}"
        
        # Check positive quantity
        assert p.quantity >= 0.0, f"Negative quantity for {p.name}"
        
        # Check gst rate
        assert p.gst_rate in valid_gst, f"Invalid GST rate {p.gst_rate} for {p.name}"
