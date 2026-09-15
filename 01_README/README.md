# Kirana Ops Agent

An autonomous, agent-first Telegram assistant designed to help Indian kirana and supermarket owners manage daily store operations entirely through natural conversation. The agent handles billing, real-time inventory, customer credit (khata), GST tax calculations, business analytics, and instant document generation without forms, web dashboards, or rigid menu trees.

---

## 🔴 Live Demo & Submission Links

| | Link |
|---|---|
| 🤖 **Telegram Bot Handle** | [@kirana_ops_agent_bot](https://t.me/kirana_ops_agent_bot) |
| 📹 **Demo Video (4–5 min)** | [Watch on Google Drive](https://drive.google.com/file/d/13zzrDZS4OU2JlsraAPzcxfkCLz1yFBdw/view?usp=sharing) |
| 📦 **GitHub Repository** | [https://github.com/lokesh2005-gif/Kirana-ops-agent](https://github.com/lokesh2005-gif/Kirana-ops-agent) *(Private — Collaborators: `Aswath363`, `akshaiP`, `ashwanthnebula`)* |
| 📂 **Full Deliverables Folder** | [Google Drive — All Submission Docs](https://drive.google.com/drive/folders/1xDqaVU92MgW6t0KwMpIsBzOBEWmw7xOQ?usp=sharing) |
| 👤 **LinkedIn** | [Lokesh V](https://www.linkedin.com/in/lokesh-v-131913290) |

---

## 🚀 How to Use the Bot

1. **Open Telegram:** On mobile, desktop, or [web.telegram.org](https://web.telegram.org).
2. **Search for Bot:** Search for `@kirana_ops_agent_bot` and tap **Start** (or send `/start`).
3. **Chat Naturally:** Speak to the bot like a smart store manager in plain English (e.g., *"Add 20 packets of Maggi"*, *"Make a bill for Ram"*).
4. **Agent Action:** The agent reasons over your request, queries the store database, calls the required business tools, and enforces shop rules.
5. **Confirm & Finalize:** Review draft bills or khata entries and confirm when prompted.
6. **Receive Results & Documents:** Get instant confirmations, real-time balances, or auto-delivered PDF tax invoices and PPTX analytical decks.

---

## 💡 Example Everyday Use Cases

| Capability | Example Telegram Prompt |
|---|---|
| **Receive / Add Stock** | `"50 packets of Maggi came in, cost ₹12, MRP ₹14"` |
| **Check Stock / Low Stock** | `"How much Tata Salt is left?"` or `"Show low stock items"` |
| **Create Multi-Item Bill** | `"Make a bill: 2kg sugar, 1 Aashirvaad Atta 5kg, 4 Maggi, pay by UPI"` |
| **Edit Draft Bill** | `"Drop the sugar and make it 6 Maggi instead"` |
| **Prevent Overselling** | `"Bill 500 packets of Maggi"` *(Agent verifies stock and refuses if stock < 500)* |
| **Customer Khata (Credit)** | `"Add ₹500 to Ram's khata"` or `"Ram paid ₹200"` |
| **Khata Balance Check** | `"What is Ram's outstanding khata balance?"` |
| **Generate PDF Invoice** | `"Send me the invoice for that last bill as a PDF"` |
| **Generate Store Analysis** | `"Make a sales analysis deck for this month"` *(Generates 6-slide PPTX)* |
| **Set Standing Preference** | `"Set default payment mode to UPI"` or `"Set shop name to Gupta Kirana"` |
| **Start New Chat Context** | `/new` *(Clears chat context; keeps all stock, khata, and preferences intact)* |

---

## 🏗️ Agent Architecture & Harness

The project is built on an **agentic control loop** using production-grade open-source components:

- **LLM & Agent Harness:** `google-genai` Python SDK function-calling API running **Gemini 3.5 Flash** (`temperature=0.0`). The LLM dynamically selects tools, evaluates intermediate database responses, and multi-step chains calls without hardcoded if/else routing or state machines.
- **Telegram Interface:** `python-telegram-bot` (v20+ async) with `update_id` deduplication against Telegram webhook/polling retries, asynchronous message handling, typing indicators, and document dispatch.
- **Data Layer:** `SQLAlchemy` ORM with dialect-agnostic models. Uses **SQLite** (`sqlite:///kirana.db` with WAL mode) for fast local dev/testing (`sqlite:///:memory:`), and **PostgreSQL** (Neon Serverless) for cloud deployment on Render.
- **Artifact Engines:** `ReportLab` for pixel-accurate GST tax invoices (PDF) with itemized tables and HSN breakdown; `python-pptx` + `matplotlib` for dynamic 6-slide executive sales presentations (PPTX).

---

## 🔄 Agent Control Loop

```
User Message (Telegram)
  │
  ▼
[ Deduplication & Dispatch ] (bot.py: verifies update_id via deque to prevent replay)
  │
  ▼
[ Gemini Reasoning Engine ] (agent.py: system prompt + 23 registered tool schemas)
  │
  ├──► Observe user intent & memory
  ├──► Reason & select appropriate tool(s)
  ▼
[ Tool Execution Layer ] (tools.py ──► app/services/*)
  │   • Validates business invariants (stock, below-cost, GST rounding, khata balance)
  │   • Executes transactional database query (SQLAlchemy / Postgres / SQLite)
  │
  ├──► Returns structured JSON or file marker (`PDF_FILE:...` / `PPTX_FILE:...`)
  ▼
[ Gemini Synthesis ] (Iterates / chains additional tools if needed; forms plain English response)
  │
  ▼
[ Delivery ] (bot.py sends formatted message + uploads generated PDF/PPTX directly to chat)
```

---

## 🛠️ Implemented Skills & Tools (23 Active Tools)

1. **Inventory:** `search_product`, `add_product`, `receive_stock`, `get_stock`, `get_low_stock`, `list_all_products`.
2. **Billing & Checkout:** `create_bill_draft`, `add_bill_item`, `update_bill_item`, `remove_bill_item`, `get_bill_draft`, `finalize_bill`.
3. **Customer Khata:** `create_customer`, `search_customer`, `add_credit`, `record_payment`, `get_customer_balance`.
4. **Analytics & Tax:** `get_daily_sales`, `get_gst_collected`.
5. **Document Generation:** `generate_invoice_pdf` (ReportLab), `generate_sales_analysis_pptx` (python-pptx + matplotlib).
6. **Durable Memory:** `get_preference`, `set_preference`.

---

## 🛡️ Critical Hard Problems Solved

- **100% Grounding (No Hallucinations):** Strict system prompt forbids inventing prices or stock; all numbers originate from DB queries.
- **Oversell Guard at DB Layer:** Atomic conditional SQL update (`UPDATE products SET quantity = quantity - :qty WHERE id = :id AND quantity >= :qty`). Zero rows affected triggers immediate rollback and `InsufficientStockError`.
- **Statutory GST Correctness:** Python `Decimal` (`ROUND_HALF_UP`) per line item, 50/50 CGST/SGST split, HSN code tracking across 0%, 5%, 12%, and 18% slabs.
- **Multi-Turn Draft Billing:** Bills remain in `draft` status across multiple conversational turns allowing live additions, quantity modifications, and item drops. Stock decrements atomically **only** upon explicit finalization.
- **Telegram Idempotency:** Built-in `idempotency_key` tracking prevents duplicate billing or double inventory deduction on network retries.
- **Business Guardrails:** Enforces `BelowCostError` (cannot sell below cost without explicit override) and prevents khata over-settlement.
- **Durable Memory:** Preferences (payment modes, shop name, GSTIN) are stored in the database (`owner_preferences`), surviving `/new` resets and server restarts.

---

## 📹 Demo Video

A 4–5 minute end-to-end screen recording demonstrating stock intake, multi-item draft billing, bill modification, oversell guardrail, khata credit/payment cycle, PDF invoice generation, PPTX analysis deck, and durable memory across `/new` is submitted alongside this repository in the submission folder.

---

## 📂 Repository

- **GitHub:** [https://github.com/lokesh2005-gif/Kirana-ops-agent](https://github.com/lokesh2005-gif/Kirana-ops-agent)
- **Collaborators Invited:** `Aswath363`, `akshaiP`, `ashwanthnebula`
- **Test Suite:** 30 automated unit & hardening tests (`pytest tests/`) covering all concurrency, GST, oversell, and persistence invariants.
