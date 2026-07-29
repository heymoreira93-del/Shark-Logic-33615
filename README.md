# REI DealShark — Shark Mode

Hunt → Math → Kill. Streamlit + SQLite + Twilio + fpdf2.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## Dashboard

| Column | Job |
|--------|-----|
| **The Hunt** | Address, Skip Trace, seller mobile |
| **The Math** | Repair checklist, ARV confidence, comps |
| **The Kill** | Live MAO, Generate PDF, Fire SMS |

Seller opens `APP_BASE_URL/?deal_id=XXXXXXXX` → types name → `SIGNED`.

## Modules

| File | Role |
|------|------|
| `rehab.py` | Roof / Paint / Kitchen / HVAC costs |
| `comps.py` | Mock sold comps for PDF justification |
| `generator.py` | DealShark PDF (price, scope, comps, signature) |
| `db.py` | `create_deal` / `get_deal` / `mark_as_signed` |
| `comms.py` | Twilio SMS with signing URL |
| `hunter.py` | Skip trace (mock or API) |
| `logic.py` | MAO tiers |
| `cli.py` | Desk CLI |
| `app.py` | Mega-UI + Seller View |

## PDF sections

1. Purchase Price  
2. Scope of Work (checked repairs)  
3. Market Analysis (3 comps)  
4. Signature  
