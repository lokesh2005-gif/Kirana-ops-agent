# Kirana Ops Agent — Demo Script

> **Before recording:** Send one throwaway message (e.g. "hi") to the bot **60–90 seconds before you start recording**, to wake the Render instance out of free-tier sleep. Wait for its reply. Then start the actual demo so there's no dead gap on camera.

---

## Demo Flow (~4–5 min)

Send the messages below **one at a time**, waiting for the bot's reply before sending the next.

---

### 1. Receive Stock

```
50 packets of Maggi came in, cost ₹12, MRP ₹14
```
*Expected: Bot calls `search_product("Maggi")`, then `receive_stock`. Confirms new stock level.*

---

### 2. Start a Multi-Item Bill

```
make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, pay by UPI
```
*Expected: Bot searches each product, creates a draft, adds 4 line items, shows the draft summary with GST breakdown. Does NOT finalize yet — waits for confirmation.*

---

### 3. Edit the Bill

```
drop the butter and make it 6 Maggi instead
```
*Expected: Bot removes the butter item, updates Maggi qty to 6, shows revised draft. Stock still untouched.*

---

### 4. Confirm & Finalize

```
looks good, finalize it
```
*Expected: Bot finalizes, stock decrements atomically, shows bill number, total, CGST, SGST.*

---

### 5. Oversell Attempt (Guardrail Demo)

```
make a new bill for 200 packets of Maggi, cash
```
*Expected: Bot tries to finalize, oversell guard triggers (stock < 200), returns clear error message. Stock stays at whatever is left.*

---

### 6. Khata — Add Credit

```
add ₹500 to Ram's khata
```
*If Ram doesn't exist:* `create a customer called Ram`  
*Then:* `add ₹500 credit to Ram`  
*Expected: Credit logged. Bot confirms new balance.*

---

### 7. Khata — Record Payment

```
Ram paid ₹200
```
*Expected: Payment recorded. Bot shows new balance (₹300).*

---

### 8. Khata — Balance Check

```
what's Ram's khata balance?
```
*Expected: Bot calls `get_customer_balance`, returns ₹300.*

---

### 9. PDF Invoice

```
send me the invoice for that last bill as a PDF
```
*Expected: Bot calls `generate_invoice_pdf` with the bill ID from step 4, Telegram sends a PDF file. Open it on screen to show the line-item table, GST breakup, and totals.*

---

### 10. PPTX Analysis Deck

```
make a sales analysis deck for this month
```
*Expected: Bot calls `generate_sales_analysis_pptx` with date range, Telegram sends a PPTX file. Open it to show the bar chart, stock health pie, GST slide, insights slide.*

---

### 11. Set a Standing Preference

```
set default payment mode to UPI
```
*Expected: Bot calls `set_preference("default_payment_mode", "UPI")`. Confirms.*

---

### 12. /new — Clear Conversation

Send the command:
```
/new
```
*Expected: Bot confirms conversation cleared. No products, customers, or preferences are touched — only the in-memory chat context.*

---

### 13. Prove Preference Persisted (Memory Survives /new)

```
make a quick bill: 1 Tata salt, finalize
```
*Expected: Bot searches for Tata Salt, creates draft, and when finalizing it reads `get_preference("default_payment_mode")` → returns "UPI" → uses UPI without asking. This proves the preference lives in the DB, not the conversation.*

---

## What This Demonstrates (SPEC.md checklist)

| Capability | Step |
|-----------|------|
| Receive stock | 1 |
| Multi-item bill (multi-turn, editable) | 2, 3 |
| Finalize with stock decrement | 4 |
| Oversell guard enforced at DB layer | 5 |
| Khata credit / payment / balance | 6, 7, 8 |
| PDF invoice (real ReportLab document) | 9 |
| PPTX analysis deck (real charts) | 10 |
| Set preference (durable memory) | 11 |
| /new clears only conversation, not data | 12 |
| Preference survives /new + restart | 13 |
