from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, Index
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    sku = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    category = Column(String)
    unit = Column(String, nullable=False) # kg/g/l/ml/packet/dozen/piece
    is_loose = Column(Boolean, default=False, nullable=False)
    cost_price = Column(Float, nullable=False)
    sell_price = Column(Float, nullable=False)
    mrp = Column(Float)
    quantity = Column(Float, nullable=False, default=0.0)
    reorder_level = Column(Float, default=0.0)
    gst_rate = Column(Float, nullable=False) # 0, 5, 12, 18
    hsn_code = Column(String)

class Customer(Base):
    __tablename__ = 'customers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)

class Bill(Base):
    __tablename__ = 'bills'
    
    id = Column(Integer, primary_key=True)
    bill_number = Column(String, unique=True, index=True, nullable=False)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=True)
    status = Column(String, nullable=False, default='draft') # draft/finalized/void
    subtotal = Column(Float, default=0.0)
    cgst_total = Column(Float, default=0.0)
    sgst_total = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    payment_mode = Column(String)
    payment_reference = Column(String)
    idempotency_key = Column(String, unique=True, index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finalized_at = Column(DateTime, nullable=True)

    items = relationship("BillItem", back_populates="bill")
    customer = relationship("Customer")

class BillItem(Base):
    __tablename__ = 'bill_items'
    
    id = Column(Integer, primary_key=True)
    bill_id = Column(Integer, ForeignKey('bills.id'), nullable=False)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    gst_rate = Column(Float, nullable=False)
    taxable_amount = Column(Float, nullable=False)
    cgst_amount = Column(Float, nullable=False)
    sgst_amount = Column(Float, nullable=False)
    line_total = Column(Float, nullable=False)

    bill = relationship("Bill", back_populates="items")
    product = relationship("Product")

class StockTransaction(Base):
    __tablename__ = 'stock_transactions'
    
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey('products.id'), nullable=False)
    change_qty = Column(Float, nullable=False)
    reason = Column(String, nullable=False) # receive/sale/adjustment
    reference_id = Column(String) # bill id etc
    created_at = Column(DateTime, default=datetime.utcnow)

class KhataTransaction(Base):
    __tablename__ = 'khata_transactions'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    amount = Column(Float, nullable=False) # +credit/-payment
    type = Column(String, nullable=False)
    note = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class OwnerPreference(Base):
    __tablename__ = 'owner_preferences'
    
    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(String)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
