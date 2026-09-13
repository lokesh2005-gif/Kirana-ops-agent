import os
import csv
from app.db.models import Product, Base
from app.db.database import engine, SessionLocal

def seed_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    
    # Locate data/products.csv relative to project root
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    csv_path = os.path.join(base_dir, "data", "products.csv")
    
    if os.path.exists(csv_path):
        with open(csv_path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sku = row["sku"].strip()
                existing = db.query(Product).filter(Product.sku == sku).first()
                if not existing:
                    prod = Product(
                        sku=sku,
                        name=row["name"].strip(),
                        category=row["category"].strip(),
                        unit=row["unit"].strip(),
                        is_loose=row["is_loose"].strip().lower() == "true",
                        cost_price=float(row["cost_price"]),
                        sell_price=float(row["sell_price"]),
                        mrp=float(row["mrp"]) if row.get("mrp") else None,
                        quantity=float(row["quantity"]),
                        reorder_level=float(row["reorder_level"]),
                        gst_rate=float(row["gst_rate"]),
                        hsn_code=row.get("hsn_code", "").strip() or None,
                    )
                    db.add(prod)
        db.commit()
    db.close()

if __name__ == "__main__":
    seed_db()
    print("Database seeded with 50 supermarket products.")
