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
    """Gets the khata (credit) balance for a customer."""
    db = SessionLocal()
    try:
        balance = khata.get_balance(db, customer_id)
        return f"Current balance for customer {customer_id}: {balance}"
    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        db.close()

# List of all tools for the agent
ALL_TOOLS = [
    search_product, add_product, receive_stock, get_stock, create_bill_draft,
    add_bill_item, update_bill_item, remove_bill_item, finalize_bill,
    get_preference, set_preference, get_customer_balance
]
