# AGENTS.md

## What this is
**DealShark SaaS** — production stack is Next.js (`apps/web`) on Vercel + Supabase Auth/Postgres/Edge Functions.

Legacy Streamlit (`app.py`) is local/reference only. Do not add new production features to Streamlit.

## Services
- **Web:** `npm --prefix apps/web run dev` (port 3000)
- **Supabase:** schema in `supabase/migrations`, functions in `supabase/functions`
- **Legacy Streamlit (optional):** `python3 -m streamlit run app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true`

## Secrets
- Never commit `.env` / `.env.local` / `.streamlit/secrets.toml`
- Production secrets live in **Vercel Environment Variables** and **Supabase Function Secrets**
- Templates: `.env.example`, `apps/web/.env.example`

## Verify
```bash
bash scripts/verify-saas.sh
```

## Hello-world (SaaS)
1. Set `apps/web/.env.local` from `.env.example` with Supabase project values
2. `npm --prefix apps/web run dev`
3. Open `/signup` → create workspace → Calculator → save lead → Deals → create deal → open sign link
