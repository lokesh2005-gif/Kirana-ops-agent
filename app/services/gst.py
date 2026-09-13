from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple

def compute_line_tax(unit_price: float, qty: float, gst_rate: float) -> Tuple[float, float, float, float]:
    price = Decimal(str(unit_price))
    quantity = Decimal(str(qty))
    
    # The taxable amount for the line
    taxable_amount = price * quantity
    taxable_amount = taxable_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    rate = Decimal(str(gst_rate)) / Decimal('100')
    
    # Calculate tax based on taxable amount
    total_tax = taxable_amount * rate
    total_tax = total_tax.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Split into CGST and SGST
    cgst = (total_tax / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    sgst = total_tax - cgst
    
    total = taxable_amount + total_tax
    
    return float(taxable_amount), float(cgst), float(sgst), float(total)
