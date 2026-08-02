#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/web"

echo "==> Typecheck / production build"
export NEXT_PUBLIC_APP_URL="${NEXT_PUBLIC_APP_URL:-https://build-verify.dealshark.app}"
export APP_URL="${APP_URL:-$NEXT_PUBLIC_APP_URL}"
export NEXT_PUBLIC_SUPABASE_URL="${NEXT_PUBLIC_SUPABASE_URL:-https://example.supabase.co}"
export NEXT_PUBLIC_SUPABASE_ANON_KEY="${NEXT_PUBLIC_SUPABASE_ANON_KEY:-build-placeholder-anon-key-000000000000}"
export NODE_ENV=production

npm run build

echo "==> Health route module present"
test -f src/app/api/health/route.ts

echo "==> Edge functions present"
for fn in health send-sms rentcast-proxy stripe-webhook sign-deal; do
  test -f "$ROOT/supabase/functions/$fn/index.ts"
  echo "  ok $fn"
done

echo "==> No committed secrets"
if git -C "$ROOT" ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "ERROR: .env is tracked" >&2
  exit 1
fi

echo "SaaS verify: BUILD OK"
