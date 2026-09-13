from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.models import Customer, KhataTransaction
from typing import Optional

def create_customer(db: Session, name: str, phone: Optional[str] = None) -> Customer:
    c = Customer(name=name, phone=phone)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c

def search_customer(db: Session, query: str) -> list[Customer]:
    search_term = f"%{query}%"
    return db.query(Customer).filter(Customer.name.ilike(search_term)).all()

def get_khata_summary(db: Session, customer_id: int) -> dict:
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise ValueError(f"Customer ID {customer_id} not found")
        
    credits = db.query(func.sum(KhataTransaction.amount)).filter(
        KhataTransaction.customer_id == customer_id, 
        KhataTransaction.type == 'credit'
    ).scalar() or 0.0
    
    payments = db.query(func.sum(KhataTransaction.amount)).filter(
        KhataTransaction.customer_id == customer_id, 
        KhataTransaction.type == 'payment'
    ).scalar() or 0.0
    
    balance = credits - payments
    return {
        "customer_id": c.id,
        "customer_name": c.name,
        "phone": c.phone,
        "total_credit": float(round(credits, 2)),
        "total_payment": float(round(payments, 2)),
        "outstanding_balance": float(round(balance, 2)),
        "formula": f"Total Credit (₹{credits:.2f}) - Total Payment (₹{payments:.2f}) = Outstanding Balance (₹{balance:.2f})"
    }

def get_balance(db: Session, customer_id: int) -> float:
    return get_khata_summary(db, customer_id)["outstanding_balance"]

def add_credit(db: Session, customer_id: int, amount: float, note: Optional[str] = None) -> KhataTransaction:
    if amount <= 0:
        raise ValueError("Amount must be positive")
    
    c = db.query(Customer).filter(Customer.id == customer_id).first()
    if not c:
        raise ValueError("Customer not found")
        
    txn = KhataTransaction(
        customer_id=customer_id,
        amount=amount,
        type="credit",
        note=note
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn

def record_payment(db: Session, customer_id: int, amount: float) -> KhataTransaction:
    if amount <= 0:
        raise ValueError("Amount must be positive")
        
    balance = get_balance(db, customer_id)
    if balance == 0:
        raise ValueError("Cannot record payment for customer with no outstanding credit")
        
    if amount > balance:
        raise ValueError(f"Cannot record payment larger than current balance ({balance})")
        
    txn = KhataTransaction(
        customer_id=customer_id,
        amount=amount,
        type="payment"
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn
