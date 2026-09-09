# Day 1 Acceptance Criteria Checklist — LegalMetrix AI

The Day 1 milestone ("Requirements, Rule Mapping and System Design") is evaluated against the following strict acceptance criteria:

| # | Acceptance Criterion | Status | Verification Detail |
|---|---|:---:|---|
| 1 | Backend application initializes & runs | `PASSED` | FastAPI app structured in `backend/app/main.py` |
| 2 | `GET /` returns name and status | `PASSED` | Verified via unit tests (`test_health.py`) |
| 3 | `GET /health` returns healthy status | `PASSED` | Verified via unit tests (`test_health.py`) |
| 4 | PostgreSQL database configuration exists | `PASSED` | Defined in `backend/app/core/database.py` & `config.py` |
| 5 | Alembic migration framework & initial migration | `PASSED` | Initial revision `001_initial_schema.py` in `backend/alembic/versions` |
| 6 | 10 Core domain SQLAlchemy ORM models exist | `PASSED` | User, Product, ScanSession, ScanImage, OCRBlock, Declaration, ComplianceRule, ComplianceFinding, Report, AuditLog |
| 7 | Core Pydantic domain contracts exist | `PASSED` | Implemented in `backend/app/schemas/` |
| 8 | Standardized OCR output contract defined | `PASSED` | `OCRResult` with bounding boxes, confidence, engine version |
| 9 | Central declaration taxonomy configured | `PASSED` | `DeclarationType` enum and `docs/declaration-taxonomy.md` |
| 10 | Declarative compliance rule representation | `PASSED` | `RuleDefinition` JSON schema & `DeterministicRuleService` |
| 11 | Rule versioning architecture documented | `PASSED` | Documented in `docs/compliance-rule-design.md` with finding snapshots |
| 12 | Frontend React + Vite app runs & builds | `PASSED` | Verified via `npm run build` |
| 13 | 8 Planned frontend placeholder routes configured | `PASSED` | `/login`, `/dashboard`, `/scans/new`, `/products`, `/products/:id`, `/inspections/:id`, `/reports`, `/rules` |
| 14 | 7 Reusable GovTech UI component skeletons | `PASSED` | Sidebar, Navbar, KPICard, UploadZone, DeclarationCard, ViolationBadge, ConfidenceIndicator |
| 15 | Complete API contract documented | `PASSED` | Documented in `docs/api-contract.md` across 9 route groups |
| 16 | 20 Product test case scenario fixtures created | `PASSED` | `backend/tests/fixtures/product_cases.json` |
| 17 | `.env.example` files provided for Backend & Frontend | `PASSED` | `.env.example` in `backend/` and `frontend/` |
| 18 | `README.md` with setup and reproduction commands | `PASSED` | Root `README.md` with step-by-step commands and legal disclaimer |
| 19 | Secrets excluded from git repository | `PASSED` | `.gitignore` covers `.env`, logs, build artifacts, db files |
| 20 | Backend smoke tests and schema validation pass | `PASSED` | `pytest backend/tests/` passes |
| 21 | Frontend production bundle builds cleanly | `PASSED` | `npm run build` generates dist bundle with zero errors |
