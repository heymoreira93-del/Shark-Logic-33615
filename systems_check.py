"""
Stack health — Twilio / Stripe / Sheets / Email / RentCast / People-data.
Surfaces what's live vs what's blocking money today.
Never prints secret values — only key names and masked phone/mode.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

# Common Cloud-secret typos / aliases
_SECRET_ALIASES: dict[str, tuple[str, ...]] = {
    "TWILIO_ACCOUNT_SID": ("TWILIO_ACCOUNT_SID", "TWILIO_SID", "ACCOUNT_SID"),
    "TWILIO_AUTH_TOKEN": ("TWILIO_AUTH_TOKEN", "TWILIO_TOKEN", "AUTH_TOKEN"),
    "TWILIO_PHONE_NUMBER": (
        "TWILIO_PHONE_NUMBER",
        "TWILIO_FROM",
        "TWILIO_NUMBER",
        "FROM_NUMBER",
    ),
    "STRIPE_SECRET_KEY": ("STRIPE_SECRET_KEY", "STRIPE_KEY", "STRIPE_API_KEY"),
    "APP_BASE_URL": ("APP_BASE_URL", "BASE_URL", "STREAMLIT_APP_URL"),
    "RENTCAST_API_KEY": ("RENTCAST_API_KEY", "RENTCAST_KEY"),
    "EMAIL_USER": ("EMAIL_USER", "GMAIL_USER", "SMTP_USER"),
    "EMAIL_PASS": ("EMAIL_PASS", "EMAIL_PASSWORD", "GMAIL_APP_PASSWORD", "SMTP_PASS"),
    "BUYER_EMAILS": ("BUYER_EMAILS", "BUYER_EMAIL", "CASH_BUYER_EMAILS"),
    "PEOPLE_DATA_API_URL": (
        "PEOPLE_DATA_API_URL",
        "SKIP_TRACE_API_URL",
        "BATCHDATA_API_URL",
    ),
    "PEOPLE_DATA_API_KEY": (
        "PEOPLE_DATA_API_KEY",
        "SKIP_TRACE_API_KEY",
        "BATCHDATA_API_KEY",
    ),
    "GOOGLE_SHEETS_URL": ("GOOGLE_SHEETS_URL", "SHEETS_URL", "GSHEETS_URL"),
}

_PLACEHOLDERS = frozenset(
    {
        "",
        "your_key_here",
        "your_sid",
        "your_sid_here",
        "your_token",
        "your_token_here",
        "your_rentcast_key",
        "your_auth_token",
        "sk_test_...",
        "sk_live_...",
        "rk_test_...",
        "rk_live_...",
        "your_gmail_app_password",
        "xxxx_gmail_app_password_xxxx",
        "sk_live_xxxxxxxx",
        "+1xxxxxxxxxx",
        "+1XXXXXXXXXX",
        "ACxxxxxxxx",
        "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "you@gmail.com",
        "deals@yourdomain.com",
        "buyer1@example.com, buyer2@example.com",
        "paste_rentcast_key",
        "paste_twilio_auth_token",
        "paste_vendor_key",
        "sk_live_xxxxxxxx",
        "sk_test_xxxxxxxx",
    }
)


def _refresh_env_from_streamlit() -> None:
    """Pull Cloud secrets into os.environ (safe to call repeatedly)."""
    try:
        from secrets_bootstrap import bootstrap_secrets

        bootstrap_secrets()
    except Exception:
        pass


def _is_bad_secret(val: str | None) -> bool:
    """True for empty / template secrets (never treat as configured)."""
    raw = (val or "").strip()
    if not raw or raw in _PLACEHOLDERS:
        return True
    try:
        from secrets_bootstrap import is_placeholder_secret

        if is_placeholder_secret(raw):
            return True
    except Exception:
        pass
    if raw.endswith("...") and ("sk_" in raw or "rk_" in raw or "AC" in raw):
        return True
    if "xxxxxxxx" in raw.lower() or raw.endswith("XXXXXXXXXX") or raw.endswith("xxxxxxxxxx"):
        return True
    if "YOUR_SHEET_ID" in raw:
        return True
    return False


def _env(key: str) -> str:
    """Resolve canonical key, then aliases. Never injects placeholder secrets."""
    _refresh_env_from_streamlit()
    val = (os.getenv(key) or "").strip()
    if val and not _is_bad_secret(val):
        return val
    for alt in _SECRET_ALIASES.get(key, ()):
        val = (os.getenv(alt) or "").strip()
        if val and not _is_bad_secret(val):
            os.environ[key] = val
            return val
    # Also peek st.secrets directly (Cloud) if bootstrap missed nested tables
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return ""

        def _accept(raw: object) -> str:
            if raw is None:
                return ""
            cleaned = str(raw).strip().strip('"').strip("'")
            if not cleaned or _is_bad_secret(cleaned):
                return ""
            os.environ[key] = cleaned
            return cleaned

        for alt in (key,) + _SECRET_ALIASES.get(key, ()):
            try:
                raw = secrets.get(alt) if hasattr(secrets, "get") else secrets[alt]
            except Exception:
                continue
            got = _accept(raw)
            if got:
                return got
        # Nested [twilio] / [stripe] / [email] block support
        try:
            nested_sections = {
                "twilio": {
                    "TWILIO_ACCOUNT_SID": ("account_sid", "sid", "TWILIO_ACCOUNT_SID"),
                    "TWILIO_AUTH_TOKEN": ("auth_token", "token", "TWILIO_AUTH_TOKEN"),
                    "TWILIO_PHONE_NUMBER": (
                        "phone_number",
                        "from_number",
                        "TWILIO_PHONE_NUMBER",
                    ),
                },
                "stripe": {
                    "STRIPE_SECRET_KEY": ("secret_key", "STRIPE_SECRET_KEY", "api_key"),
                    "APP_BASE_URL": ("app_base_url", "APP_BASE_URL", "base_url"),
                },
                "email": {
                    "EMAIL_USER": ("user", "EMAIL_USER"),
                    "EMAIL_PASS": ("pass", "password", "EMAIL_PASS"),
                    "EMAIL_FROM": ("from", "EMAIL_FROM"),
                    "BUYER_EMAILS": ("buyers", "BUYER_EMAILS"),
                },
            }
            for section, mapping in nested_sections.items():
                if key not in mapping:
                    continue
                try:
                    block = secrets[section]
                except Exception:
                    continue
                for nested_key in mapping[key]:
                    try:
                        raw = block[nested_key]
                    except Exception:
                        continue
                    got = _accept(raw)
                    if got:
                        return got
        except Exception:
            pass
    except Exception:
        pass
    return ""


def _has(key: str) -> bool:
    val = _env(key)
    return bool(val) and not _is_bad_secret(val)


def _missing(keys: list[str]) -> list[str]:
    return [k for k in keys if not _has(k)]


def _normalize_from(phone: str) -> str:
    p = (phone or "").strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if p.startswith("++"):
        p = "+" + p[2:]
    if p and not p.startswith("+") and p.isdigit():
        if len(p) == 10:
            p = "+1" + p
        elif len(p) == 11 and p.startswith("1"):
            p = "+" + p
    return p


def _mask_phone(phone: str) -> str:
    if len(phone) >= 6:
        return phone[:2] + "****" + phone[-4:]
    return "+****"


def twilio_status() -> dict[str, Any]:
    sid = _has("TWILIO_ACCOUNT_SID")
    token = _has("TWILIO_AUTH_TOKEN")
    from_raw = _env("TWILIO_PHONE_NUMBER")
    from_n = _normalize_from(from_raw)
    ok_from = bool(from_n) and from_n.startswith("+") and not from_n.startswith("++")
    placeholder_from = from_raw in _PLACEHOLDERS or from_raw.endswith("xxxxxxxxxx")
    if placeholder_from:
        ok_from = False
    # Persist normalized from-number so SMS send uses it
    if ok_from and from_n != from_raw:
        os.environ["TWILIO_PHONE_NUMBER"] = from_n
    ready = bool(sid and token and ok_from)
    missing: list[str] = []
    notes: list[str] = []
    if not sid:
        missing.append("TWILIO_ACCOUNT_SID")
        notes.append("Missing TWILIO_ACCOUNT_SID (must start with AC...)")
    if not token:
        missing.append("TWILIO_AUTH_TOKEN")
        notes.append("Missing TWILIO_AUTH_TOKEN")
    if not ok_from:
        missing.append("TWILIO_PHONE_NUMBER")
        notes.append(
            "Missing/invalid TWILIO_PHONE_NUMBER — use E.164 like +18881234567 "
            "(one plus, no spaces)."
        )
    else:
        notes.append(f"From number OK ({_mask_phone(from_n)})")
    notes.append(
        "Cloud: paste TOP-LEVEL key names (TWILIO_ACCOUNT_SID=...), then Reboot app."
    )
    notes.append(
        "Trial SMS only reaches Verified Caller IDs. Register 10DLC for real blasts."
    )
    return {
        "ready": ready,
        "label": "Twilio SMS",
        "notes": notes,
        "missing": missing,
        "mode": "live" if ready else "off",
    }


def stripe_status() -> dict[str, Any]:
    from payments import stripe_mode

    key_ok = _has("STRIPE_SECRET_KEY")
    base_ok = _has("APP_BASE_URL")
    mode = stripe_mode() if key_ok else "off"
    # Configured enough to run checkout (test OR live)
    ready = bool(key_ok and base_ok)
    missing: list[str] = []
    notes: list[str] = []
    if not key_ok:
        missing.append("STRIPE_SECRET_KEY")
        notes.append("Missing STRIPE_SECRET_KEY (use sk_live_... for real money)")
    if not base_ok:
        missing.append("APP_BASE_URL")
        notes.append("Missing APP_BASE_URL (no trailing slash)")
        notes.append(
            "WARN: empty APP_BASE_URL — outsiders get broken links. "
            "Set APP_BASE_URL=https://realestateshark.streamlit.app (no trailing slash)"
        )
    else:
        base = _env("APP_BASE_URL").rstrip("/")
        os.environ["APP_BASE_URL"] = base
        notes.append(f"APP_BASE_URL={base}")
        if _env("APP_BASE_URL") != base:
            notes.append("Trailing slash stripped from APP_BASE_URL")
        try:
            from secrets_bootstrap import is_localhost_base_url

            localish = is_localhost_base_url(base)
        except Exception:
            localish = "localhost" in base.lower() or "127.0.0.1" in base
        if localish:
            notes.append(
                "WARN: APP_BASE_URL is localhost — Stripe/SMS/email links will not work "
                "for outsiders. Set APP_BASE_URL=https://realestateshark.streamlit.app"
            )
    if mode == "test":
        notes.append(
            "TEST MODE (sk_test_/rk_test_) — no real charges. "
            "Swap to sk_live_/rk_live_ for production money."
        )
    elif mode == "live":
        notes.append("LIVE MODE — real card charges. Finish Stripe Activate if locked.")
    elif key_ok:
        notes.append("Key present but not sk_/rk_ prefix — verify it is a secret key.")
    return {
        "ready": ready,
        "label": "Stripe EMD",
        "notes": notes,
        "missing": missing,
        "mode": mode,
        "production_ready": mode == "live" and ready,
    }


def sheets_status() -> dict[str, Any]:
    try:
        from sheets_vault import sheets_configured

        ready = sheets_configured()
    except Exception:
        ready = False
    missing: list[str] = []
    notes: list[str] = []
    if not ready:
        has_url = _has("GOOGLE_SHEETS_URL")
        url_val = _env("GOOGLE_SHEETS_URL")
        if "YOUR_SHEET_ID" in (url_val or ""):
            has_url = False
        has_conn = False
        has_sa = False
        try:
            import streamlit as st

            secrets = getattr(st, "secrets", None)
            if secrets is not None:
                if "connections" in secrets and "gsheets" in secrets["connections"]:
                    try:
                        g = secrets["connections"]["gsheets"]
                        sheet = g.get("spreadsheet") if hasattr(g, "get") else g["spreadsheet"]
                        sheet_s = str(sheet or "").strip()
                        has_conn = bool(sheet_s) and "YOUR_SHEET_ID" not in sheet_s
                    except Exception:
                        has_conn = False
                has_sa = "gcp_service_account" in secrets
        except Exception:
            pass
        if not has_url and not has_conn:
            missing.append("GOOGLE_SHEETS_URL / [connections.gsheets]")
        if not has_sa:
            missing.append("[gcp_service_account] or st-gsheets connection")
        notes.append(
            "Needs [connections.gsheets] spreadsheet URL + service account shared on tab 'Leads'."
        )
        notes.append("Falls back to local CRM if Sheets is off.")
        notes.append("Placeholder YOUR_SHEET_ID does not count as configured.")
    else:
        notes.append("Sheets vault configured — writes go to Google + local CRM mirror.")
    return {
        "ready": ready,
        "label": "Google Sheets Vault",
        "notes": notes,
        "missing": missing,
        "mode": "live" if ready else "local",
    }


def email_status() -> dict[str, Any]:
    try:
        from email_blast import email_configured

        ready = email_configured()
    except Exception:
        ready = False
    missing = _missing(["EMAIL_USER", "EMAIL_PASS", "BUYER_EMAILS"])
    # BUYER_EMAILS may be present but empty / example-only after split
    buyers = [
        e for e in (_env("BUYER_EMAILS") or "").replace(";", ",").split(",") if e.strip()
    ]
    if not buyers and "BUYER_EMAILS" not in missing:
        missing.append("BUYER_EMAILS")
    if buyers and all("example.com" in b for b in buyers):
        if "BUYER_EMAILS" not in missing:
            missing.append("BUYER_EMAILS")
    notes: list[str] = []
    if not ready:
        if missing:
            notes.append(f"Missing: {', '.join(missing)}")
        notes.append("Need EMAIL_USER, EMAIL_PASS (Gmail App Password), BUYER_EMAILS")
        notes.append("Rejects example.com buyers and placeholder App Passwords.")
    else:
        notes.append(f"Configured for {len(buyers)} buyer recipient(s)")
    notes.append("Use a deals@ mailbox + App Password so blasts don't hit spam.")
    return {
        "ready": ready,
        "label": "Buyer Email Blast",
        "notes": notes,
        "missing": missing if not ready else [],
        "mode": "live" if ready else "off",
    }


def rentcast_status() -> dict[str, Any]:
    from data_engine import has_rentcast_key

    ready = has_rentcast_key()
    missing = [] if ready else ["RENTCAST_API_KEY"]
    notes = [
        "Powers live ARV/comps + Seller Factory + owner name skip-trace.",
        "Does NOT return cell phones.",
    ]
    if not ready:
        notes.insert(0, "Missing RENTCAST_API_KEY — app will use MOCK property/comps.")
    else:
        notes.insert(0, "Live RentCast ON — no silent mock when API returns data.")
    return {
        "ready": ready,
        "label": "RentCast Data",
        "notes": notes,
        "missing": missing,
        "mode": "live" if ready else "mock",
    }


def people_data_status() -> dict[str, Any]:
    from phone_enrich import people_data_configured

    ready = people_data_configured()
    missing = [] if ready else ["PEOPLE_DATA_API_URL", "PEOPLE_DATA_API_KEY"]
    notes = [
        "Optional: PEOPLE_DATA_API_URL + PEOPLE_DATA_API_KEY for cell enrichment.",
        "Aliases: SKIP_TRACE_API_URL / SKIP_TRACE_API_KEY also accepted.",
        "Without it: paste phones manually / CSV import.",
    ]
    return {
        "ready": ready,
        "label": "People-Data Phones",
        "notes": notes,
        "missing": missing,
        "mode": "live" if ready else "manual",
        "optional": True,
    }


def full_stack_report() -> list[dict[str, Any]]:
    _refresh_env_from_streamlit()
    return [
        rentcast_status(),
        twilio_status(),
        stripe_status(),
        sheets_status(),
        email_status(),
        people_data_status(),
    ]


def missing_keys_summary() -> list[str]:
    """Flat list of missing required (non-optional) secret names."""
    keys: list[str] = []
    for row in full_stack_report():
        if row.get("optional"):
            continue
        for k in row.get("missing") or []:
            if k not in keys:
                keys.append(k)
    return keys


CLOUD_SECRETS_TOML_TEMPLATE = '''# === DealShark Streamlit Cloud Secrets (PLACEHOLDERS ONLY) ===
# App settings → Secrets → paste → Save → Reboot app
# Do NOT commit real values.

# REQUIRED — public app URL, NO trailing slash. Never localhost.
APP_BASE_URL = "https://realestateshark.streamlit.app"

RENTCAST_API_KEY = "paste_rentcast_key"

TWILIO_ACCOUNT_SID = "ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
TWILIO_AUTH_TOKEN = "paste_twilio_auth_token"
TWILIO_PHONE_NUMBER = "+1XXXXXXXXXX"
TWILIO_AGENT_PHONE = "+1XXXXXXXXXX"
NOTIFY_PHONE = "+1XXXXXXXXXX"
# Optional War Room click-to-call webhook:
# TWILIO_VOICE_WEBHOOK = "https://your-twilio-function.twil.io/conference"

# PRODUCTION money: sk_live_... (or rk_live_...). sk_test_ = demo charges only.
STRIPE_SECRET_KEY = "sk_live_xxxxxxxx"
STRIPE_EMD_CENTS = "250000"

EMAIL_USER = "you@gmail.com"
EMAIL_PASS = "xxxx_gmail_app_password_xxxx"
EMAIL_FROM = "deals@yourdomain.com"
BUYER_EMAILS = "buyer1@example.com, buyer2@example.com"

WIRE_BANK = "Your Title Company Escrow"
WIRE_ACCOUNT = "xxxx"
WIRE_ROUTING = "xxxx"
TITLE_COMPANY_NAME = "ABC Title / Escrow"

GOOGLE_SHEETS_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"

# Optional cell enrichment (not RentCast):
# PEOPLE_DATA_API_URL = "https://api.vendor.com/lookup?name={name}&address={address}&api_key={api_key}"
# PEOPLE_DATA_API_KEY = "paste_vendor_key"

[connections.gsheets]
spreadsheet = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"

# Uncomment and paste full Google Cloud service-account JSON fields:
# [gcp_service_account]
# type = "service_account"
# project_id = "your-project"
# private_key_id = "..."
# private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
# client_email = "....iam.gserviceaccount.com"
# client_id = "..."
# token_uri = "https://oauth2.googleapis.com/token"
'''


def render_systems_check() -> None:
    import streamlit as st

    st.subheader("Stack Status — Money Blockers")
    report = full_stack_report()
    cols = st.columns(3)
    for i, row in enumerate(report):
        with cols[i % 3]:
            if row["ready"]:
                mode = row.get("mode") or ""
                suffix = f" ({mode})" if mode and mode not in ("live", "on") else ""
                st.success(f"ON · {row['label']}{suffix}")
            else:
                opt = " (optional)" if row.get("optional") else ""
                st.error(f"OFF · {row['label']}{opt}")
            missing = row.get("missing") or []
            if missing:
                st.caption("Missing keys: " + ", ".join(missing))
            for n in row.get("notes") or []:
                st.caption(n)

    # Stripe force-live warning
    stripe = next((r for r in report if r["label"] == "Stripe EMD"), None)
    if stripe and stripe.get("ready") and stripe.get("mode") == "test":
        st.warning(
            "Stripe is ON but in TEST mode — buyers will not pay real money. "
            "Replace STRIPE_SECRET_KEY with sk_live_... (or rk_live_...), Save Secrets, Reboot."
        )
    if stripe and stripe.get("mode") == "live" and not stripe.get("production_ready"):
        st.warning("Stripe live key detected but APP_BASE_URL is missing.")

    base_raw = (_env("APP_BASE_URL") or "").strip()
    try:
        from secrets_bootstrap import is_localhost_base_url

        base_local = is_localhost_base_url(base_raw)
    except Exception:
        base_local = (not base_raw) or ("localhost" in base_raw.lower())
    if base_local:
        st.warning(
            "APP_BASE_URL is missing or localhost — other people cannot open deal/Stripe links. "
            "In Cloud Secrets set:\n"
            'APP_BASE_URL = "https://realestateshark.streamlit.app"\n'
            "(no trailing slash). Others must open https://realestateshark.streamlit.app — not localhost."
        )

    all_missing = missing_keys_summary()
    if all_missing:
        st.error("Required secrets still missing (names only — values never shown):")
        st.code("\n".join(all_missing), language="text")

    tw = next((r for r in report if r["label"] == "Twilio SMS"), None)
    if tw and not tw["ready"]:
        st.warning(
            "Twilio is OFF. Paste TOP-LEVEL names into Streamlit Cloud → Settings → Secrets, "
            "then **Reboot** the app:"
        )
        st.code(
            'TWILIO_ACCOUNT_SID = "ACxxxxxxxx"\n'
            'TWILIO_AUTH_TOKEN = "your_auth_token"\n'
            'TWILIO_PHONE_NUMBER = "+18881234567"',
            language="toml",
        )

    with st.expander("Full Cloud Secrets TOML (placeholders only)", expanded=False):
        st.code(CLOUD_SECRETS_TOML_TEMPLATE, language="toml")
        st.caption(
            "After paste: Save → Manage app → Reboot. "
            "Twilio 10DLC required for bulk SMS. Prefer email blast until registered."
        )

    st.markdown(
        """
**Legal reality:** Assignment / offer PDFs are **operational templates**.
Have a Florida-licensed attorney and your title company review before live closings.
Title is your paymaster — disbursement language only works if they accept it.
        """
    )
