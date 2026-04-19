# TrendSense Project Restructuring (System Architecture)

This plan outlines the steps to reorganize the TrendSense codebase into a modular, professional system architecture. The goal is to separate concerns, improve maintainability, and unify shared logic (database, config) while mitigating common Python project pitfalls.

## User Review Required

> [!IMPORTANT]
> **Python Path & Imports**: To avoid `ModuleNotFoundError`, all components will now be treated as parts of a single package. You should run services using `python -m services.tiktok-scraper.scraper_main` from the root directory.
> **Deployment Updates**: I will update the GitHub Actions workflows and Modal configuration, but you may need to re-verify secret names if any change.
> **Database Refactor**: I am moving from single files to a modular `core/db` structure (models + sessions).

## Proposed Changes

### 1. New Directory Structure
The project will be organized as follows:

- `backend/` -> FastAPI service (Web API).
- `frontend/` -> Next.js service (Web UI).
- `services/` -> Independent processing components.
    - `ai-engine/` (from `src/ai_core`)
    - `tiktok-scraper/` (from `src/scraper`)
- `core/` -> Shared logic (The heart of the system).
    - `db/` -> Database layer.
        - `models.py` (Table definitions and SQL queries)
        - `session.py` (Connection pooling/factory)
    - `config/` -> Layered configuration.
        - `base.py` (Shared variables like `DATABASE_URL`)
        - `backend_settings.py` (API specific)
        - `service_settings.py` (Scraper/AI specific)
    - `utils/` (Shared utilities)
- `scripts/` -> Management and legacy scripts.
    - `legacy_dashboard/` (moved from `src/dashboard`)
- `docs/` -> Documentation.
- `data/` -> Local data storage.

---

### 2. File Relocations & Refactoring

#### [NEW] `core/db/`
- **`models.py`**: Extract all SQL logic.
- **`session.py`**: A unified **Sync** `get_connection()` function using `psycopg2`. No async boilerplate for now.

#### [NEW] `core/config/`
- **`base.py`**: Core environment loading.
- **`backend_settings.py`**: Inherits from base.
- **`service_settings.py`**: Inherits from base.

#### [NEW] Separate Requirements
- **`backend/requirements.txt`**: FastAPI, Uvicorn, etc.
- **`services/tiktok-scraper/requirements.txt`**: Selenium, Scrapy/BS4, etc.
- **`services/ai-engine/requirements.txt`**: Modal, NLP/AI tools.

#### [MOVE] `src/ai_core/*` -> `services/ai-engine/*`
#### [MOVE] `src/scraper/*` -> `services/tiktok-scraper/*`
#### [MOVE] `src/dashboard/app.py` -> `scripts/legacy_dashboard/app.py`
#### [MOVE] `run.py`, `run_project.bat` -> `scripts/`

---

### 3. Import & Package Updates
- Add `__init__.py` **only** to Python-related directories (`core`, `backend`, `services`).
- Global update of imports to absolute style: `from core.db import session`.
- Update `PYTHONPATH` instructions for running services.

### 4. Deployment & CI/CD Updates
- **GitHub Actions**: Update `working-directory` and command paths in `.github/workflows/ai_pipeline.yml` and `weekly_train.yml`.
- **Modal**: Update any file reference in `modal_app.py` to the new `services/ai-engine/` path.

---

## Open Questions

- None. Ready to execute.
