import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.models import Bill, BillItem, Product, StockTransaction
from app.services.gst import compute_line_tax

class InsufficientStockError(Exception):
    pass

class BelowCostError(Exception):
    pass

def generate_bill_number() -> str:
    return f"INV-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

def create_draft(db: Session, customer_id: Optional[int] = None) -> Bill:
    bill = Bill(
        bill_number=generate_bill_number(),
        customer_id=customer_id,
        status="draft"
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)
    return bill

def add_item(db: Session, bill_id: int, product_id: int, qty: float) -> BillItem:
    bill = db.query(Bill).filter(Bill.id == bill_id, Bill.status == 'draft').first()
    if not bill:
        raise ValueError("Draft bill not found")
        
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ValueError("Product not found")
        
    if product.quantity < qty:
        # Soft advisory check - we don't raise here so draft can be created,
        # but the agent can see this later or it fails at finalize.
        pass
        
    taxable, cgst, sgst, total = compute_line_tax(product.sell_price, qty, product.gst_rate)
    
    item = BillItem(
        bill_id=bill_id,
        product_id=product_id,
        quantity=qty,
        unit_price=product.sell_price,
        gst_rate=product.gst_rate,
        taxable_amount=taxable,
        cgst_amount=cgst,
        sgst_amount=sgst,
        line_total=total
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def update_item(db: Session, item_id: int, qty: float) -> BillItem:
    item = db.query(BillItem).filter(BillItem.id == item_id).first()
    if not item:
        raise ValueError("Bill item not found")
    
    bill = db.query(Bill).filter(Bill.id == item.bill_id, Bill.status == 'draft').first()
    if not bill:
        raise ValueError("Draft bill not found")
        
    product = db.query(Product).filter(Product.id == item.product_id).first()
    
    taxable, cgst, sgst, total = compute_line_tax(item.unit_price, qty, item.gst_rate)
    item.quantity = qty
    item.taxable_amount = taxable
    item.cgst_amount = cgst
    item.sgst_amount = sgst
    item.line_total = total
    
    db.commit()
    db.refresh(item)
    return item

def remove_item(db: Session, item_id: int):
    item = db.query(BillItem).filter(BillItem.id == item_id).first()
    if not item:
        raise ValueError("Bill item not found")
    
    bill = db.query(Bill).filter(Bill.id == item.bill_id, Bill.status == 'draft').first()
    if not bill:
        raise ValueError("Draft bill not found")
        
    db.delete(item)
    db.commit()

def finalize(db: Session, bill_id: int, payment_mode: str, payment_reference: Optional[str] = None, idempotency_key: Optional[str] = None, override_price_check: bool = False) -> Bill:
    if idempotency_key:
        existing = db.query(Bill).filter(Bill.idempotency_key == idempotency_key, Bill.status == 'finalized').first()
        if existing:
            return existing

    bill = db.query(Bill).filter(Bill.id == bill_id).first()
    if not bill or bill.status != 'draft':
        raise ValueError("Bill not found or not in draft status")

    items = db.query(BillItem).filter(BillItem.bill_id == bill_id).all()
    if not items:
        raise ValueError("Cannot finalize empty bill")

    try:
        subtotal = 0.0
        cgst_total = 0.0
        sgst_total = 0.0
        total = 0.0

        for item in items:
            product = db.query(Product).filter(Product.id == item.product_id).first()
            if not override_price_check and item.unit_price < product.cost_price:
                raise BelowCostError(f"Selling {product.name} below cost price.")

            # Atomic decrement
            result = db.execute(
                text("UPDATE products SET quantity = quantity - :qty WHERE id = :id AND quantity >= :qty"),
                {"qty": item.quantity, "id": item.product_id}
            )
            
            if result.rowcount == 0:
                # Need to refresh to get latest quantity for error message
                db.expire(product)
                raise InsufficientStockError(f"Insufficient stock for {product.name}. Available: {product.quantity}")

            # Log transaction
            txn = StockTransaction(
                product_id=item.product_id,
                change_qty=-item.quantity,
                reason="sale",
                reference_id=str(bill.id)
            )
            db.add(txn)

            subtotal += item.taxable_amount
            cgst_total += item.cgst_amount
            sgst_total += item.sgst_amount
            total += item.line_total

        bill.status = 'finalized'
        bill.finalized_at = datetime.utcnow()
        bill.subtotal = round(subtotal, 2)
        bill.cgst_total = round(cgst_total, 2)
        bill.sgst_total = round(sgst_total, 2)
        bill.total = round(total, 2)
        bill.payment_mode = payment_mode
        bill.payment_reference = payment_reference
        if idempotency_key:
            bill.idempotency_key = idempotency_key
            
        db.commit()
        db.refresh(bill)
        return bill
    except Exception as e:
        db.rollback()
        raise e
