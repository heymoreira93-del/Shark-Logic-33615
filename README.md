# DealShark SaaS

Production wholesaling OS: **Next.js (Vercel) + Supabase Auth/DB/Edge Functions**.

The legacy Streamlit app (`app.py`) remains for local reference only. New production work targets `apps/web` and `supabase/`.

## Architecture

| Layer | Tech |
|---|---|
| Frontend + API routes | Next.js App Router on Vercel (`apps/web`) |
| Auth / Postgres / RLS | Supabase Production |
| Secrets | Vercel env + Supabase Function secrets (never committed) |
| Edge Functions | `send-sms`, `rentcast-proxy`, `stripe-webhook`, `sign-deal`, `health` |
| Logging | Structured JSON via `pino` + Edge `console` JSON |
| Errors | Sentry (`SENTRY_DSN` / `NEXT_PUBLIC_SENTRY_DSN`) |

## Multi-tenant model

Every company is an `organizations` row. Users join via `organization_members` with a `roles` assignment. Capabilities come from `permissions` / `role_permissions`.

Tenant tables (all include `organization_id`):

- `organization_members` (users in the company)
- `leads`, `deals`, `contacts`, `files`
- `organization_settings`, `offer_queue`, `audit_logs`

App queries go through `tenantFrom()` / `requireOrgContext()` so `organization_id` is always applied. Postgres RLS (`is_org_member`, `has_org_permission`) blocks cross-org access even if app code regresses.

## AuthZ (roles + permissions)

Roles: **Owner**, **Admin**, **Manager**, **Employee**, **Viewer**

Permissions:

| Key | Label |
|---|---|
| `leads.view` | View Leads |
| `leads.edit` | Edit Leads |
| `leads.delete` | Delete Leads |
| `deals.view` | View Deals |
| `deals.edit` | Edit Deals |
| `users.manage` | Manage Users |
| `billing.manage` | Billing |
| `settings.manage` | Settings |

- Pages use `requirePageAuth(...)` and redirect to `/dashboard/unauthorized` when denied.
- APIs use `requireApiAuth(...)` and return `{ error, code }` with **no data** on 401/403.
- Middleware blocks unauthenticated access to `/dashboard/*` and non-public `/api/*`.

## Required production env

See `.env.example` and `apps/web/.env.example`. There are **no localhost defaults** in production.

Minimum:

- `NEXT_PUBLIC_APP_URL` / `APP_URL` — Vercel HTTPS URL
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- Twilio / Stripe / RentCast / Sentry as needed

## Deploy

### 1) Supabase

```bash
npx supabase login
npx supabase link --project-ref YOUR_PROJECT_REF
npx supabase db push
npx supabase secrets set TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=... TWILIO_PHONE_NUMBER=... RENTCAST_API_KEY=... STRIPE_SECRET_KEY=... STRIPE_WEBHOOK_SECRET=... NOTIFY_PHONE=...
npx supabase functions deploy health send-sms rentcast-proxy stripe-webhook sign-deal
```

### 2) Vercel

```bash
npx vercel link
npx vercel env pull   # or set in dashboard from apps/web/.env.example
npx vercel --prod
```

Point Supabase Auth redirect URLs to `https://YOUR_VERCEL_DOMAIN/auth/callback`.

### 3) Verify

```bash
curl -sS https://YOUR_VERCEL_DOMAIN/api/health
```

Then: sign up → create deal → open `/sign/<token>` → confirm SIGNED in dashboard.

## Local SaaS dev

```bash
cd apps/web
cp .env.example .env.local   # fill with Supabase prod or local values
npm install
npm run dev
```

## Security notes

- Secrets never live in git. `.env` is gitignored.
- Seller e-sign uses unguessable `sign_token` (not raw deal id alone for public access).
- Stripe EMD is marked paid only via webhook signature verification.
- RLS scopes leads/deals to the user's organization.
