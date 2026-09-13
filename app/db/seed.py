from app.db.models import Product, Base
from app.db.database import engine, SessionLocal

def seed_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Avoid duplicating if already seeded
    if db.query(Product).count() > 0:
        db.close()
        return

    products = [
        # Loose items (0% GST)
        Product(sku="LOOSE-SUGAR", name="Sugar (Loose)", category="Staples", unit="kg", is_loose=True, cost_price=35.0, sell_price=42.0, mrp=45.0, quantity=50.0, reorder_level=10.0, gst_rate=0.0, hsn_code="1701"),
        Product(sku="LOOSE-RICE", name="Rice (Loose)", category="Staples", unit="kg", is_loose=True, cost_price=40.0, sell_price=55.0, mrp=60.0, quantity=100.0, reorder_level=20.0, gst_rate=0.0, hsn_code="1006"),
        Product(sku="LOOSE-DAL", name="Toor Dal (Loose)", category="Staples", unit="kg", is_loose=True, cost_price=90.0, sell_price=110.0, mrp=120.0, quantity=30.0, reorder_level=5.0, gst_rate=0.0, hsn_code="0713"),
        
        # Packaged staples (5% GST)
        Product(sku="ATTA-AASH-5KG", name="Aashirvaad Atta 5kg", category="Packaged", unit="packet", is_loose=False, cost_price=180.0, sell_price=210.0, mrp=230.0, quantity=20.0, reorder_level=5.0, gst_rate=5.0, hsn_code="1101"),
        Product(sku="SALT-TATA-1KG", name="Tata Salt 1kg", category="Packaged", unit="packet", is_loose=False, cost_price=15.0, sell_price=24.0, mrp=25.0, quantity=50.0, reorder_level=10.0, gst_rate=5.0, hsn_code="2501"),
        Product(sku="OIL-FORT-1L", name="Fortune Sunflower Oil 1L", category="Packaged", unit="litre", is_loose=False, cost_price=110.0, sell_price=140.0, mrp=150.0, quantity=40.0, reorder_level=10.0, gst_rate=5.0, hsn_code="1512"),
        
        # FMCG (12-18% GST)
        Product(sku="AMUL-BTR-100G", name="Amul Butter 100g", category="FMCG", unit="packet", is_loose=False, cost_price=45.0, sell_price=54.0, mrp=56.0, quantity=30.0, reorder_level=10.0, gst_rate=12.0, hsn_code="0405"),
        Product(sku="MAGGI-70G", name="Maggi 70g", category="FMCG", unit="packet", is_loose=False, cost_price=12.0, sell_price=14.0, mrp=14.0, quantity=100.0, reorder_level=20.0, gst_rate=18.0, hsn_code="1902"),
        Product(sku="PARLE-G", name="Parle-G", category="FMCG", unit="packet", is_loose=False, cost_price=4.0, sell_price=5.0, mrp=5.0, quantity=200.0, reorder_level=50.0, gst_rate=18.0, hsn_code="1905"),
        Product(sku="SURF-EXCEL", name="Surf Excel", category="FMCG", unit="packet", is_loose=False, cost_price=150.0, sell_price=185.0, mrp=190.0, quantity=25.0, reorder_level=5.0, gst_rate=18.0, hsn_code="3402"),
    ]
    
    db.add_all(products)
    db.commit()
    db.close()

if __name__ == "__main__":
    seed_db()
    print("Database seeded.")
