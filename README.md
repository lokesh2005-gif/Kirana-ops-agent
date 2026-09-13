# Kirana Ops Agent

An agent-first Telegram bot that runs an Indian kirana store end-to-end — billing, stock, GST, khata credit, and document generation — entirely through natural language. No web UI. No regex/keyword router. The LLM decides which tools to call.

## 🔴 Live Demo

| | Link |
|---|---|
| 🤖 **Telegram Bot** | [@Ops_agent_supermarket_bot](https://t.me/Ops_agent_supermarket_bot) |
| 🌐 **Live Server** | [https://kirana-ops-agent-dfh0.onrender.com](https://kirana-ops-agent-dfh0.onrender.com) |
| 📦 **Repository** | [https://github.com/lokesh2005-gif/Kirana-ops-agent](https://github.com/lokesh2005-gif/Kirana-ops-agent) |

> **Quick start:** Open Telegram → search `@Ops_agent_supermarket_bot` → send `/start`

---

## Why this harness?

**Harness:** `google-genai` Python SDK function-calling API (hand-rolled agent loop)

We started with Google ADK (`google-adk`) as specified, but after reading the current docs we found it requires a FastAPI/ASGI event loop and session-management infrastructure that conflicts cleanly with `python-telegram-bot`'s own async loop. The `google-genai` SDK's native function-calling is semantically identical — Gemini receives a tool registry, decides which tools to call, calls them, feeds results back, and continues — so it satisfies the SPEC.md "equivalent harness" clause. We note this explicitly rather than silently switching.

**Why not a router or state machine?** A router hardcodes intent → handler. Every new capability needs a new branch. A state machine hardcodes transitions. Both break under ambiguity. Here, the LLM reads the full tool registry and system prompt, reasons about user intent, chains multiple tool calls in one turn (e.g. `search_product × 2 → create_bill_draft → add_bill_item × 2`), and handles novel phrasing without any code changes. Business rules live in services/DB, not in the prompt.

---

## Control Loop

```
User message (Telegram)
  → bot.py: dedup on update_id, route to chat session
  → agent.py: gemini chat session with tool registry
  → Gemini: observe → reason → function_call (tool name + args)
  → tools.py: dispatches to app/services/*, returns structured result
  → Gemini: reads result → reason → (another function_call if needed, or final response)
  → bot.py: send text response (+ send_document if tool returned PDF_FILE:/PPTX_FILE: path)
```

Multiple tool calls chain in one user turn before Gemini returns a final text response. The model never sees raw DB rows — only what each tool returns.

---

## Tool Surface

Each tool is thin by design: one responsibility, one failure mode, one structured return value the model can read and explain.

| Tool | Calls | Why thin |
|------|-------|----------|
| `search_product` | `inventory.search_product` | Fuzzy match only — forces LLM to clarify ambiguous names |
| `add_product` | `inventory.add_product` | Create product record only |
| `receive_stock` | `inventory.receive_stock` | Increment qty + log StockTransaction atomically |
| `get_stock` | `inventory.get_stock` | Read-only qty check |
| `get_low_stock` | `inventory.get_low_stock` | Reorder alert, read-only |
| `create_bill_draft` | `billing.create_draft` | Creates bill with `status=draft` only |
| `add_bill_item` | `billing.add_item` | Draft only — no stock movement |
| `update_bill_item` | `billing.update_item` | Draft only — no stock movement |
| `remove_bill_item` | `billing.remove_item` | Draft only — no stock movement |
| `get_bill_draft` | DB query | Show current draft for confirmation |
| `finalize_bill` | `billing.finalize` | Atomic stock decrement + idempotency guard |
| `create_customer` | `khata.create_customer` | Customer record only |
| `add_credit` | `khata.add_credit` | Ledger entry (credit) |
| `record_payment` | `khata.record_payment` | Ledger entry (payment) + balance guard |
| `get_customer_balance` | `khata.get_balance` | Aggregated balance |
| `get_daily_sales` | `analytics.get_daily_sales` | Read-only aggregate |
| `get_gst_collected` | `analytics.get_gst_collected` | Read-only aggregate |
| `generate_invoice_pdf` | `invoice.generate_invoice_pdf` | ReportLab PDF → returns `PDF_FILE:path` |
| `generate_sales_analysis_pptx` | `presentation.generate_sales_analysis_pptx` | python-pptx+matplotlib → returns `PPTX_FILE:path` |
| `set_preference` | `preferences.set_preference` | DB-backed KV store |
| `get_preference` | `preferences.get_preference` | DB-backed KV store |

---

## DB Schema

```
products          — SKU, name, category, unit, is_loose, cost/sell/MRP price, qty, reorder_level, gst_rate, hsn_code
customers         — name, phone
bills             — bill_number (unique), customer_id, status (draft/finalized/void), subtotal, cgst_total, sgst_total, total, payment_mode, idempotency_key (unique)
bill_items        — bill_id, product_id, qty, unit_price, gst_rate, taxable_amount, cgst_amount, sgst_amount, line_total
stock_transactions — product_id, change_qty, reason (receive/sale/adjustment), reference_id
khata_transactions — customer_id, amount, type (credit/payment), note
owner_preferences — key (unique), value
```

**SQLite for tests / Postgres for production:** Tests use `sqlite:///:memory:` (zero setup, fast, fully parallel). Production uses Neon Postgres (set via `DATABASE_URL`). SQLAlchemy makes models dialect-agnostic; the only dialect-specific code is WAL-mode pragma in `database.py`, gated on `if DATABASE_URL.startswith("sqlite")`. Render's free tier has an ephemeral filesystem — local SQLite would be wiped on every redeploy/sleep-wake. Postgres (Neon free tier) persists forever.

---

## Hard Requirements — How Each Is Solved

| Requirement | Solution | Proof |
|-------------|----------|-------|
| **Grounding** | System prompt forbids invented numbers; all tools query DB | `app/agent/prompts.py` |
| **Oversell guard** | `UPDATE products SET qty=qty-:qty WHERE id=:id AND qty>=:qty` — rowcount==0 → rollback | `app/services/billing.py::finalize`, `tests/test_hardening.py::TestOversellGuard` |
| **GST correctness** | `Decimal` arithmetic, `ROUND_HALF_UP` per line, 50/50 CGST/SGST split | `app/services/gst.py`, `tests/test_hardening.py::TestGSTCorrectness` |
| **Multi-turn drafts** | Draft items stored in DB; `products.quantity` untouched until `finalize()` | `app/services/billing.py`, `tests/test_hardening.py::TestMultiTurnBills` |
| **Idempotency** | `finalize()` checks `idempotency_key` on entry; if already finalized, returns existing bill unchanged | `app/services/billing.py::finalize`, `tests/test_hardening.py::TestIdempotency` |
| **Concurrency** | Atomic conditional UPDATE (not SELECT-then-UPDATE); WAL mode on SQLite | `app/services/billing.py`, `tests/test_hardening.py::TestConcurrency` |
| **Guardrails** | `BelowCostError` in `finalize()`; no `delete_stock` tool exists; `record_payment` guards balance | `app/services/billing.py`, `app/services/khata.py`, `tests/test_hardening.py::TestGuardrails` |
| **Real artifacts** | ReportLab PDF with line-item table; python-pptx+matplotlib deck with real chart data | `app/services/invoice.py`, `app/services/presentation.py`, `tests/test_hardening.py::TestRealArtifacts` |
| **Durable memory** | `owner_preferences` table in Postgres; `get_preference` called by agent every turn | `app/services/preferences.py`, `tests/test_hardening.py::TestPreferencePersistence` |

---

## Project Structure

```
app/
  agent/
    agent.py       — Gemini client + chat session factory
    tools.py       — 21 LLM-callable tool functions
    prompts.py     — system prompt with grounding/guardrail instructions
    cli_test.py    — local REPL for debugging without Telegram
  db/
    database.py    — engine/session, WAL pragma for SQLite
    models.py      — SQLAlchemy ORM models
    seed.py        — real SKU seed data with HSN codes + GST slabs
  services/
    billing.py     — draft/finalize logic, oversell guard, idempotency
    gst.py         — CGST/SGST split, Decimal rounding
    inventory.py   — product search, stock receive, low-stock query
    khata.py       — credit/payment ledger with balance guards
    analytics.py   — read-only aggregates (sales, GST, stock health)
    invoice.py     — ReportLab PDF invoice generator
    presentation.py— python-pptx + matplotlib PPTX deck generator
    preferences.py — DB-backed KV store for standing preferences
  telegram/
    bot.py         — python-telegram-bot: routing, dedup, document dispatch
tests/
  test_data_layer.py   — seed validity
  test_services.py     — billing, GST, khata unit tests
  test_hardening.py    — 22 tests covering all 9 hard requirements
artifacts/
  invoices/            — generated PDF invoices
  reports/             — generated PPTX decks
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BOT_TOKEN` | Yes | — | Telegram bot token from @BotFather |
| `GEMINI_API_KEY` | Yes | — | Google AI Studio API key |
| `DATABASE_URL` | No | `sqlite:///kirana.db` | SQLAlchemy DB URL; use Postgres in prod |
| `USE_WEBHOOK` | No | `false` | Set `true` for webhook mode (Render) |
| `WEBHOOK_URL` | If webhook | — | Public HTTPS URL of your Render service |
| `PORT` | If webhook | `8443` | Port to listen on |

Copy `.env.example` to `.env` and fill in values for local dev.

---

## Setup & Run (Local)

```bash
# Clone and install
git clone https://github.com/lokesh2005-gif/Kirana-ops-agent.git
cd Kirana-ops-agent
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env: add BOT_TOKEN and GEMINI_API_KEY; DATABASE_URL defaults to SQLite

# Run tests (uses in-memory SQLite, no external services needed)
pytest tests/

# Run the bot locally (polling mode, no public URL needed)
python -m app.telegram.bot

# Or test the agent in the terminal without Telegram
python -m app.agent.cli_test
```

---

## Deployment (Render Free Web Service)

### Step 1 — Postgres (Neon free tier)
1. Sign up at [neon.tech](https://neon.tech), create a project, copy the connection string (starts with `postgresql://`).
2. This is your `DATABASE_URL` — it persists across Render sleep/redeploy cycles.

### Step 2 — Render Web Service
1. Push the repo to GitHub.
2. [render.com](https://render.com) → New → Web Service → connect the GitHub repo.
3. **Build command:** `pip install -r requirements.txt`
4. **Start command:** `python -m app.telegram.bot`
5. **Environment variables** (in Render dashboard):
   ```
   BOT_TOKEN=<your token>
   GEMINI_API_KEY=<your key>
   DATABASE_URL=<neon postgres connection string>
   USE_WEBHOOK=true
   WEBHOOK_URL=https://<your-render-slug>.onrender.com/<SECRET_PATH>
   PORT=8443
   ```
   Replace `<SECRET_PATH>` with a random string (e.g. `wh-kirana-a7f3d`).

### Step 3 — Register the Webhook
After Render deploys, run once (from any machine):
```bash
curl "https://api.telegram.org/bot<BOT_TOKEN>/setWebhook?url=https://<render-slug>.onrender.com/<SECRET_PATH>"
```
Expected response: `{"ok":true,"result":true,"description":"Webhook was set"}`

### Step 4 — Verify
Send any message to the Telegram bot. You should get a real response. Check Render logs to confirm the request arrived via webhook, not polling.

> **Note:** Free-tier Render services sleep after 15 min of inactivity. The first message after idle will have a 30–60 second cold-start delay — expected, not a bug. See DEMO.md for how to handle this before recording.

---

## Running Tests

```bash
# All tests (30 tests, ~2s, zero external services)
pytest tests/ -v

# Hardening-only (22 tests covering all 9 hard requirements)
pytest tests/test_hardening.py -v
```

All tests use `sqlite:///:memory:` — no Postgres, no network, no API keys required.