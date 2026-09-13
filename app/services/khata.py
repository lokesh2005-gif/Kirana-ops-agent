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

def get_balance(db: Session, customer_id: int) -> float:
    # credit adds to balance, payment subtracts from it.
    credits = db.query(func.sum(KhataTransaction.amount)).filter(
        KhataTransaction.customer_id == customer_id, 
        KhataTransaction.type == 'credit'
    ).scalar() or 0.0
    
    payments = db.query(func.sum(KhataTransaction.amount)).filter(
        KhataTransaction.customer_id == customer_id, 
        KhataTransaction.type == 'payment'
    ).scalar() or 0.0
    
    return credits - payments

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
