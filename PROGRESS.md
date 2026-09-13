# Kirana Ops Agent - Progress

- [x] Phase 1: Data layer
- [x] Phase 2: Business logic + tests
- [x] Phase 3: Agent + tools
- [x] Phase 4: Telegram
- [x] Phase 5: Documents
- [x] Phase 6: Hardening
- [ ] Phase 7: README / demo / deploy

---

## Hard Requirements Verification (SPEC.md §"Hard requirements")

| # | Requirement | Test Reference | Status |
|---|-------------|----------------|--------|
| 1 | **Grounding** — prices/GST/stock always from tools/DB | System prompt enforces; all tools query DB | ✅ |
| 2 | **Oversell guard** — enforced at DB layer via atomic UPDATE | `TestOversellGuard::test_cannot_oversell`, `test_exact_stock_sells` | ✅ |
| 3 | **GST correctness** — per-item slab, CGST/SGST split, rounding | `TestGSTCorrectness` (4 tests), `test_gst_computation` | ✅ |
| 4 | **Multi-turn bills** — stock untouched until finalize | `TestMultiTurnBills::test_draft_does_not_touch_stock`, `test_stock_moves_only_on_finalize` | ✅ |
| 5 | **Idempotency** — retried finalize is a no-op | `TestIdempotency::test_double_finalize_same_key`, `test_no_duplicate_stock_transactions` | ✅ |
| 6 | **Concurrency** — atomic conditional UPDATE, no double-sell | `TestConcurrency::test_sale_vs_sale_one_succeeds`, `test_sale_and_receipt_concurrent`, `test_concurrency_oversell` | ✅ |
| 7 | **Guardrails** — no below-cost, no delete-stock, no bad khata | `TestGuardrails` (6 tests) | ✅ |
| 8 | **Real artifacts** — actual PDF + PPTX from real DB data | `TestRealArtifacts::test_pdf_invoice_generated`, `test_pptx_generated` | ✅ |
| 9 | **Durable memory** — preferences survive restart/new session | `TestPreferencePersistence` (2 tests) | ✅ |
