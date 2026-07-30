# AGENTS.md

## Cursor Cloud specific instructions

### What this is
`DealShark — Tampa Shark Mode`: a single-service **Streamlit** app (`app.py`, entrypoint also exposed via `main.py`) for real-estate wholesaling — MAO calculator, seller "War Room", and offer-contract PDF generation (SQLite for storage, `fpdf2` for PDFs). A pure-logic CLI (`cli.py`) exposes the MAO calculator.

### Services
- **Streamlit web app** (the only long-running service). Run: `python3 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true`. The `streamlit` console script installs to `~/.local/bin` (not on PATH), so invoke it via `python3 -m streamlit`.
- **CLI** (no server): e.g. `python3 cli.py --arv 300000 --sqft 1500 --fee 10000 --rehab medium`.

### Non-obvious caveats
- **All external integrations are optional and mock-fallback by default.** With no secrets, the app runs fully in "mock" mode (mock ARV/comps/skip-trace, local SQLite instead of Google Sheets, no real SMS/email/Stripe). This is the expected dev state — no secrets are needed to run or demo the app.
- **`.env` is optional.** The app reads config via `os.getenv` with placeholder filtering (`secrets_bootstrap.py`), so it runs without a `.env`. Copy `cp .env.example .env` only if you want to exercise a real integration; the placeholder values in `.env.example` are intentionally ignored.
- **`jinja2` is a required runtime dependency** even though it is NOT listed in `requirements.txt`. The "Generate PDF" / agreement-preview flow uses pandas `.style`, which raises `AttributeError: The '.style' accessor requires jinja2` without it. The update script installs it. It is imported lazily at PDF time, so you can `pip install jinja2` into a running server without restarting.
- **`requirements.txt` has a dependency conflict**: it pins `gspread>=6.0.0`, but `st-gsheets-connection==0.1.0` requires `gspread<6`. `pip install -r requirements.txt` therefore fails to resolve. `gspread` is only a transitive dep (code imports `streamlit_gsheets`, never `gspread` directly), so installing the packages while letting `st-gsheets-connection` pick its own `gspread` (5.x) works fine. The update script handles this.
- SQLite DB files (`deals.db`, `tampa_leads.db`, `crm.db`) and generated `contracts/*.pdf` are created at runtime in the repo root and are gitignored.

### Lint / test / build
- No test suite or lint config exists in the repo. Use `python3 -m py_compile *.py` as a basic syntax/compile check.
- There is no separate build step (Streamlit runs the source directly).

### Hello-world (verifies core functionality)
Open `http://localhost:8501/` → Calculator tab → type a Property Address → "Pull Live Data" (mock) → enter a Seller Name → "Generate PDF". A "PDF ready: /workspace/contracts/...OFFER.pdf" success box confirms the MAO calc + deal creation + PDF generation path works end-to-end.
