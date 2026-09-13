from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import date, datetime
from typing import List, Dict, Any
from app.db.models import Bill, BillItem, Product

def get_daily_sales(db: Session, target_date: date) -> Dict[str, Any]:
    # Query finalized bills for a specific date
    result = db.query(
        func.count(Bill.id).label("bill_count"),
        func.sum(Bill.total).label("total_sales")
    ).filter(
        Bill.status == 'finalized',
        cast(Bill.finalized_at, Date) == target_date
    ).first()
    
    return {
        "date": target_date,
        "bill_count": result.bill_count or 0,
        "total_sales": float(result.total_sales or 0.0)
    }

def get_sales_summary(db: Session, start_date: date, end_date: date) -> Dict[str, Any]:
    result = db.query(
        func.count(Bill.id).label("bill_count"),
        func.sum(Bill.total).label("total_sales")
    ).filter(
        Bill.status == 'finalized',
        cast(Bill.finalized_at, Date) >= start_date,
        cast(Bill.finalized_at, Date) <= end_date
    ).first()
    
    return {
        "start_date": start_date,
        "end_date": end_date,
        "bill_count": result.bill_count or 0,
        "total_sales": float(result.total_sales or 0.0)
    }

def get_top_products(db: Session, start_date: date, end_date: date, n: int = 5) -> List[Dict[str, Any]]:
    # Sum quantity from bill items within date range
    results = db.query(
        Product.name,
        func.sum(BillItem.quantity).label("total_qty")
    ).join(BillItem, Product.id == BillItem.product_id)\
     .join(Bill, Bill.id == BillItem.bill_id)\
     .filter(
        Bill.status == 'finalized',
        cast(Bill.finalized_at, Date) >= start_date,
        cast(Bill.finalized_at, Date) <= end_date
    ).group_by(Product.id, Product.name)\
     .order_by(func.sum(BillItem.quantity).desc())\
     .limit(n).all()
     
    return [{"name": r.name, "qty": float(r.total_qty)} for r in results]

def get_stock_health(db: Session) -> Dict[str, Any]:
    low_stock = db.query(func.count(Product.id)).filter(Product.quantity <= Product.reorder_level).scalar() or 0
    total = db.query(func.count(Product.id)).scalar() or 0
    return {
        "total_products": total,
        "low_stock_products": low_stock,
        "healthy_products": total - low_stock
    }

def get_gst_collected(db: Session, start_date: date, end_date: date) -> Dict[str, float]:
    result = db.query(
        func.sum(Bill.cgst_total).label("cgst"),
        func.sum(Bill.sgst_total).label("sgst")
    ).filter(
        Bill.status == 'finalized',
        cast(Bill.finalized_at, Date) >= start_date,
        cast(Bill.finalized_at, Date) <= end_date
    ).first()
    
    return {
        "cgst": float(result.cgst or 0.0),
        "sgst": float(result.sgst or 0.0),
        "total": float((result.cgst or 0.0) + (result.sgst or 0.0))
    }
