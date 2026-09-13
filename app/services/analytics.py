from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import date, datetime
from typing import List, Dict, Any
from app.db.models import Bill, BillItem, Product

def get_daily_sales(db: Session, target_date: date) -> Dict[str, Any]:
    all_bills = db.query(Bill).filter(Bill.status == 'finalized').all()
    bills = [b for b in all_bills if b.finalized_at and b.finalized_at.date() == target_date]

    bill_count = len(bills)
    total_sales = sum(b.total for b in bills)
    subtotal = sum(b.subtotal for b in bills)
    cgst_total = sum(b.cgst_total for b in bills)
    sgst_total = sum(b.sgst_total for b in bills)

    total_cost = 0.0
    for bill in bills:
        for item in bill.items:
            cost = item.product.cost_price if item.product else 0.0
            total_cost += item.quantity * cost

    direct_profit = subtotal - total_cost
    profit_margin = (direct_profit / subtotal * 100.0) if subtotal > 0 else 0.0

    return {
        "date": target_date,
        "bill_count": bill_count,
        "total_sales": float(round(total_sales, 2)),
        "subtotal_excl_gst": float(round(subtotal, 2)),
        "total_cost": float(round(total_cost, 2)),
        "direct_profit": float(round(direct_profit, 2)),
        "profit_margin_percent": float(round(profit_margin, 2)),
        "total_gst": float(round(cgst_total + sgst_total, 2)),
        "cgst": float(round(cgst_total, 2)),
        "sgst": float(round(sgst_total, 2)),
        "formula": f"Net Revenue (₹{subtotal:.2f}) - Total Cost (₹{total_cost:.2f}) = Direct Profit (₹{direct_profit:.2f})"
    }

def get_sales_summary(db: Session, start_date: date, end_date: date) -> Dict[str, Any]:
    all_bills = db.query(Bill).filter(Bill.status == 'finalized').all()
    bills = [b for b in all_bills if b.finalized_at and start_date <= b.finalized_at.date() <= end_date]

    bill_count = len(bills)
    total_sales = sum(b.total for b in bills)
    subtotal = sum(b.subtotal for b in bills)
    cgst_total = sum(b.cgst_total for b in bills)
    sgst_total = sum(b.sgst_total for b in bills)

    total_cost = 0.0
    for bill in bills:
        for item in bill.items:
            cost = item.product.cost_price if item.product else 0.0
            total_cost += item.quantity * cost

    direct_profit = subtotal - total_cost
    profit_margin = (direct_profit / subtotal * 100.0) if subtotal > 0 else 0.0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "bill_count": bill_count,
        "total_sales": float(round(total_sales, 2)),
        "subtotal_excl_gst": float(round(subtotal, 2)),
        "total_cost": float(round(total_cost, 2)),
        "direct_profit": float(round(direct_profit, 2)),
        "profit_margin_percent": float(round(profit_margin, 2)),
        "total_gst": float(round(cgst_total + sgst_total, 2)),
        "cgst": float(round(cgst_total, 2)),
        "sgst": float(round(sgst_total, 2)),
        "formula": f"Net Revenue (₹{subtotal:.2f}) - Total Cost (₹{total_cost:.2f}) = Direct Profit (₹{direct_profit:.2f})"
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
