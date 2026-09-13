from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from app.db.models import Product, StockTransaction

def search_product(db: Session, query: str) -> List[Product]:
    search_term = f"%{query}%"
    return db.query(Product).filter(
        or_(
            Product.name.ilike(search_term),
            Product.sku.ilike(search_term)
        )
    ).limit(10).all()

def add_product(db: Session, sku: str, name: str, category: str, unit: str, is_loose: bool,
                cost_price: float, sell_price: float, gst_rate: float,
                mrp: Optional[float] = None, reorder_level: float = 0.0,
                hsn_code: Optional[str] = None) -> Product:
    prod = Product(
        sku=sku, name=name, category=category, unit=unit, is_loose=is_loose,
        cost_price=cost_price, sell_price=sell_price, mrp=mrp,
        quantity=0.0, reorder_level=reorder_level, gst_rate=gst_rate, hsn_code=hsn_code
    )
    db.add(prod)
    db.commit()
    db.refresh(prod)
    return prod

def receive_stock(db: Session, product_id: int, qty: float, cost_price: Optional[float] = None) -> Product:
    if qty <= 0:
        raise ValueError("Receive quantity must be positive")
    
    prod = db.query(Product).filter(Product.id == product_id).with_for_update().first()
    if not prod:
        raise ValueError("Product not found")
        
    prod.quantity += qty
    if cost_price is not None:
        prod.cost_price = cost_price
        
    txn = StockTransaction(
        product_id=product_id,
        change_qty=qty,
        reason="receive"
    )
    db.add(txn)
    db.commit()
    db.refresh(prod)
    return prod

def get_stock(db: Session, product_id: int) -> float:
    prod = db.query(Product).filter(Product.id == product_id).first()
    if not prod:
        raise ValueError("Product not found")
    return prod.quantity

def get_low_stock(db: Session) -> List[Product]:
    return db.query(Product).filter(Product.quantity <= Product.reorder_level).all()
