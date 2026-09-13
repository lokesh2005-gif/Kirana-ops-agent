import json
from datetime import date
from typing import Optional

from app.db.database import SessionLocal
from app.services import inventory, billing, khata, analytics, preferences

def search_product(query: str) -> str:
    """Searches for a product by name, sku, or aliases to find its product_id and details. Use this to avoid guessing product IDs."""
    db = SessionLocal()
    try:
        results = inventory.search_product(db, query)
        if not results:
            return "No matching products found. Ask the user for clarification."
        return json.dumps([{"id": p.id, "name": p.name, "sku": p.sku, "quantity": p.quantity, "sell_price": p.sell_price, "unit": p.unit} for p in results])
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def add_product(sku: str, name: str, category: str, unit: str, is_loose: bool, cost_price: float, sell_price: float, gst_rate: float, mrp: Optional[float] = None, reorder_level: float = 0.0, hsn_code: Optional[str] = None) -> str:
    """Adds a new product to the inventory database."""
    db = SessionLocal()
    try:
        p = inventory.add_product(db, sku, name, category, unit, is_loose, cost_price, sell_price, gst_rate, mrp, reorder_level, hsn_code)
        return f"Product added successfully. ID: {p.id}, Name: {p.name}"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def receive_stock(product_id: int, qty: float, cost_price: Optional[float] = None) -> str:
    """Receives stock for an existing product and increments its quantity."""
    db = SessionLocal()
    try:
        p = inventory.receive_stock(db, product_id, qty, cost_price)
        return f"Stock received. New quantity for {p.name} is {p.quantity}."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def get_stock(product_id: int) -> str:
    """Gets the current stock quantity for a product."""
    db = SessionLocal()
    try:
        qty = inventory.get_stock(db, product_id)
        return f"Current stock: {qty}"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def list_all_products(category: Optional[str] = None) -> str:
    """Lists all products in the store inventory with their ID, name, category, stock quantity, and selling price. Use when the user asks to see all items or products in inventory."""
    db = SessionLocal()
    try:
        results = inventory.list_all_products(db, category=category)
        if not results:
            return "No products found in inventory."
        return json.dumps([{"id": p.id, "name": p.name, "category": p.category, "quantity": p.quantity, "unit": p.unit, "sell_price": p.sell_price, "cost_price": p.cost_price} for p in results])
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def create_bill_draft(customer_id: Optional[int] = None) -> str:
    """Creates a new draft bill. Call this first when starting a new billing flow."""
    db = SessionLocal()
    try:
        bill = billing.create_draft(db, customer_id)
        return f"Draft bill created successfully. Bill ID: {bill.id}"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def add_bill_item(bill_id: int, product_id: int, qty: float) -> str:
    """Adds an item to a draft bill."""
    db = SessionLocal()
    try:
        item = billing.add_item(db, bill_id, product_id, qty)
        return f"Item added to bill {bill_id}. Line ID: {item.id}, Line Total: {item.line_total} (includes {item.cgst_amount} CGST + {item.sgst_amount} SGST)"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def update_bill_item(item_id: int, qty: float) -> str:
    """Updates the quantity of an existing item in a draft bill."""
    db = SessionLocal()
    try:
        item = billing.update_item(db, item_id, qty)
        return f"Item {item_id} updated. New Line Total: {item.line_total}"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def remove_bill_item(item_id: int) -> str:
    """Removes an item from a draft bill."""
    db = SessionLocal()
    try:
        billing.remove_item(db, item_id)
        return f"Item {item_id} removed from bill."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def finalize_bill(bill_id: int, payment_mode: str, payment_reference: Optional[str] = None, idempotency_key: Optional[str] = None, override_price_check: bool = False) -> str:
    """Finalizes a draft bill, atomically decrementing stock and recording the transaction. Requires user confirmation before calling."""
    db = SessionLocal()
    try:
        bill = billing.finalize(db, bill_id, payment_mode, payment_reference, idempotency_key, override_price_check)
        return f"Bill {bill.bill_number} finalized successfully! Total: {bill.total} (CGST: {bill.cgst_total}, SGST: {bill.sgst_total}). Payment mode: {payment_mode}."
    except Exception as e:
        return f"Error finalizing bill: {str(e)}"
    finally:
        db.close()

def get_preference(key: str) -> str:
    """Retrieves a store preference by key (e.g., 'default_payment_mode', 'default_brand')."""
    db = SessionLocal()
    try:
        val = preferences.get_preference(db, key)
        return json.dumps({"key": key, "value": val})
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def set_preference(key: str, value: str) -> str:
    """Sets a store preference."""
    db = SessionLocal()
    try:
        preferences.set_preference(db, key, value)
        return f"Preference '{key}' set to '{value}'."
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def get_customer_balance(customer_id: int) -> str:
    """Gets the khata (credit) balance and transaction summary for a customer."""
    db = SessionLocal()
    try:
        summary = khata.get_khata_summary(db, customer_id)
        return json.dumps(summary)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def generate_invoice_pdf(bill_id: int) -> str:
    """Generates a PDF GST invoice for a finalized bill and returns the file path. Use when the user asks for a bill/invoice as a PDF document."""
    try:
        from app.services.invoice import generate_invoice_pdf as _gen
        path = _gen(bill_id)
        return f"PDF_FILE:{path}"
    except Exception as e:
        return f"Error generating PDF: {str(e)}"

def generate_sales_analysis_pptx(start_date: str, end_date: str) -> str:
    """Generates a PPTX sales analysis deck for a date range (YYYY-MM-DD format) with charts and insights. Returns the file path."""
    try:
        from datetime import date
        from app.services.presentation import generate_sales_analysis_pptx as _gen
        sd = date.fromisoformat(start_date)
        ed = date.fromisoformat(end_date)
        path = _gen(sd, ed)
        return f"PPTX_FILE:{path}"
    except Exception as e:
        return f"Error generating PPTX: {str(e)}"

def get_bill_draft(bill_id: int) -> str:
    """Returns all items in a draft bill for review before finalizing."""
    db = SessionLocal()
    try:
        from app.db.models import Bill, BillItem, Product
        bill = db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            return "Bill not found."
        items = db.query(BillItem).filter(BillItem.bill_id == bill_id).all()
        if not items:
            return f"Bill {bill_id} is empty."
        lines = [f"Bill #{bill.bill_number} [{bill.status}]"]
        for it in items:
            prod = db.query(Product).filter(Product.id == it.product_id).first()
            lines.append(f"  - {prod.name if prod else it.product_id}: {it.quantity} x Rs.{it.unit_price} = Rs.{it.line_total} (Item ID: {it.id})")
        lines.append(f"  Subtotal: Rs.{bill.subtotal}  CGST: Rs.{bill.cgst_total}  SGST: Rs.{bill.sgst_total}  Total: Rs.{bill.total}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def create_customer(name: str, phone: str = None) -> str:
    """Creates a new customer for the khata ledger."""
    db = SessionLocal()
    try:
        c = khata.create_customer(db, name, phone)
        return f"Customer created. ID: {c.id}, Name: {c.name}"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def search_customer(name_or_phone: str) -> str:
    """Searches for a customer by name or phone to find their customer_id and current khata balance."""
    db = SessionLocal()
    try:
        customers = khata.search_customer(db, name_or_phone)
        if not customers:
            return "No customer found matching that name or phone."
        results = [khata.get_khata_summary(db, c.id) for c in customers]
        return json.dumps(results)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def add_credit(customer_id: int, amount: float, note: str = None) -> str:
    """Adds credit (khata) to a customer's account."""
    db = SessionLocal()
    try:
        khata.add_credit(db, customer_id, amount, note)
        summary = khata.get_khata_summary(db, customer_id)
        return json.dumps(summary)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def record_payment(customer_id: int, amount: float) -> str:
    """Records a payment against a customer's khata balance."""
    db = SessionLocal()
    try:
        khata.record_payment(db, customer_id, amount)
        summary = khata.get_khata_summary(db, customer_id)
        return json.dumps(summary)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def get_low_stock() -> str:
    """Returns all products at or below their reorder level."""
    db = SessionLocal()
    try:
        prods = inventory.get_low_stock(db)
        if not prods:
            return "All products are above reorder levels."
        return json.dumps([{"id": p.id, "name": p.name, "quantity": p.quantity, "reorder_level": p.reorder_level} for p in prods])
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def get_daily_sales(target_date: str) -> str:
    """Gets the total sales summary for a given date (YYYY-MM-DD)."""
    db = SessionLocal()
    try:
        from datetime import date
        d = date.fromisoformat(target_date)
        result = analytics.get_daily_sales(db, d)
        return json.dumps(result, default=str)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

def get_gst_collected(start_date: str, end_date: str) -> str:
    """Gets GST collected between two dates (YYYY-MM-DD)."""
    db = SessionLocal()
    try:
        from datetime import date
        sd = date.fromisoformat(start_date)
        ed = date.fromisoformat(end_date)
        result = analytics.get_gst_collected(db, sd, ed)
        return json.dumps(result)
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

# List of all tools for the agent
ALL_TOOLS = [
    search_product, add_product, receive_stock, get_stock, get_low_stock, list_all_products,
    create_bill_draft, add_bill_item, update_bill_item, remove_bill_item,
    get_bill_draft, finalize_bill,
    create_customer, search_customer, add_credit, record_payment, get_customer_balance,
    get_daily_sales, get_gst_collected,
    generate_invoice_pdf, generate_sales_analysis_pptx,
    get_preference, set_preference,
]
