"""
Stack health — Twilio / Stripe / Sheets / Email / RentCast / People-data.
Surfaces what's live vs what's blocking money today.
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
}


def _refresh_env_from_streamlit() -> None:
    """Pull Cloud secrets into os.environ (safe to call repeatedly)."""
    try:
        from secrets_bootstrap import bootstrap_secrets

        bootstrap_secrets()
    except Exception:
        pass


def _env(key: str) -> str:
    """Resolve canonical key, then aliases."""
    _refresh_env_from_streamlit()
    val = (os.getenv(key) or "").strip()
    if val:
        return val
    for alt in _SECRET_ALIASES.get(key, ()):
        val = (os.getenv(alt) or "").strip()
        if val:
            os.environ[key] = val
            return val
    # Also peek st.secrets directly (Cloud) if bootstrap missed nested tables
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is None:
            return ""
        for alt in (key,) + _SECRET_ALIASES.get(key, ()):
            try:
                raw = secrets.get(alt) if hasattr(secrets, "get") else secrets[alt]
            except Exception:
                continue
            if raw is not None and str(raw).strip():
                os.environ[key] = str(raw).strip()
                return str(raw).strip()
        # Nested [twilio] block support
        try:
            tw = secrets["twilio"]
            nested_map = {
                "TWILIO_ACCOUNT_SID": ("account_sid", "sid", "TWILIO_ACCOUNT_SID"),
                "TWILIO_AUTH_TOKEN": ("auth_token", "token", "TWILIO_AUTH_TOKEN"),
                "TWILIO_PHONE_NUMBER": (
                    "phone_number",
                    "from_number",
                    "TWILIO_PHONE_NUMBER",
                ),
            }
            for nested_key in nested_map.get(key, ()):
                try:
                    raw = tw[nested_key]
                except Exception:
                    continue
                if raw is not None and str(raw).strip():
                    os.environ[key] = str(raw).strip()
                    return str(raw).strip()
        except Exception:
            pass
    except Exception:
        pass
    return ""


def _has(key: str) -> bool:
    val = _env(key)
    return bool(val) and val not in {
        "your_key_here",
        "your_sid",
        "your_sid_here",
        "your_token",
        "your_token_here",
        "your_rentcast_key",
        "sk_test_...",
        "your_gmail_app_password",
        "+1xxxxxxxxxx",
    }


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


def twilio_status() -> dict[str, Any]:
    sid = _has("TWILIO_ACCOUNT_SID")
    token = _has("TWILIO_AUTH_TOKEN")
    from_raw = _env("TWILIO_PHONE_NUMBER")
    from_n = _normalize_from(from_raw)
    ok_from = bool(from_n) and from_n.startswith("+") and not from_n.startswith("++")
    # Persist normalized from-number so SMS send uses it
    if ok_from and from_n != from_raw:
        os.environ["TWILIO_PHONE_NUMBER"] = from_n
    ready = bool(sid and token and ok_from)
    notes = []
    if not sid:
        notes.append("Missing TWILIO_ACCOUNT_SID (must start with AC...)")
    if not token:
        notes.append("Missing TWILIO_AUTH_TOKEN")
    if not ok_from:
        notes.append(
            "Missing/invalid TWILIO_PHONE_NUMBER — use E.164 like +18881234567 "
            "(one plus, no spaces)."
        )
    else:
        # Show masked from number only
        masked = from_n[:2] + "****" + from_n[-4:] if len(from_n) >= 6 else "+****"
        notes.append(f"From number OK ({masked})")
    notes.append(
        "Cloud: Settings → Secrets must include the 3 keys as TOP-LEVEL names "
        "(not only inside a [twilio] table unless you use that format)."
    )
    notes.append(
        "Trial accounts can ONLY text Verified Caller IDs. Upgrade / 10DLC for blasts."
    )
    return {"ready": ready, "label": "Twilio SMS", "notes": notes}


def stripe_status() -> dict[str, Any]:
    ready = _has("STRIPE_SECRET_KEY") and _has("APP_BASE_URL")
    notes = []
    if not _has("STRIPE_SECRET_KEY"):
        notes.append("Missing STRIPE_SECRET_KEY in Cloud Secrets")
    if not _has("APP_BASE_URL"):
        notes.append("Missing APP_BASE_URL (no trailing slash)")
    else:
        notes.append(f"APP_BASE_URL={_env('APP_BASE_URL').rstrip('/')}")
    return {"ready": ready, "label": "Stripe EMD", "notes": notes}


def sheets_status() -> dict[str, Any]:
    try:
        from sheets_vault import sheets_configured

        ready = sheets_configured()
    except Exception:
        ready = False
    notes = [
        "Needs [connections.gsheets] + service account shared on sheet tab 'Leads'.",
        "Falls back to local CRM if Sheets is off.",
    ]
    return {"ready": ready, "label": "Google Sheets Vault", "notes": notes}


def email_status() -> dict[str, Any]:
    ready = (
        _has("EMAIL_USER")
        and _has("EMAIL_PASS")
        and bool((_env("BUYER_EMAILS") or "").strip())
    )
    notes = []
    if not ready:
        notes.append("Need EMAIL_USER, EMAIL_PASS (Gmail App Password), BUYER_EMAILS")
    notes.append("Use a deals@ mailbox so blasts don't hit spam.")
    return {"ready": ready, "label": "Buyer Email Blast", "notes": notes}


def rentcast_status() -> dict[str, Any]:
    from data_engine import has_rentcast_key

    ready = has_rentcast_key()
    notes = [
        "Powers live ARV/comps + Seller Factory + owner name skip-trace.",
        "Does NOT return cell phones.",
    ]
    return {"ready": ready, "label": "RentCast Data", "notes": notes}


def people_data_status() -> dict[str, Any]:
    from phone_enrich import people_data_configured

    ready = people_data_configured()
    notes = [
        "Optional: PEOPLE_DATA_API_URL + PEOPLE_DATA_API_KEY for cell enrichment.",
        "Without it: paste phones manually / CSV import.",
    ]
    return {"ready": ready, "label": "People-Data Phones", "notes": notes}


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


def render_systems_check() -> None:
    import streamlit as st

    st.subheader("Stack Status — Money Blockers")
    report = full_stack_report()
    cols = st.columns(3)
    for i, row in enumerate(report):
        with cols[i % 3]:
            if row["ready"]:
                st.success(f"ON · {row['label']}")
            else:
                st.error(f"OFF · {row['label']}")
            for n in row.get("notes") or []:
                st.caption(n)

    tw = next((r for r in report if r["label"] == "Twilio SMS"), None)
    if tw and not tw["ready"]:
        st.warning(
            "Twilio is OFF. Paste this exact block into Streamlit Cloud → Settings → Secrets "
            "(replace with your real values), then **Reboot** the app:"
        )
        st.code(
            'TWILIO_ACCOUNT_SID = "ACxxxxxxxx"\n'
            'TWILIO_AUTH_TOKEN = "your_auth_token"\n'
            'TWILIO_PHONE_NUMBER = "+18881234567"',
            language="toml",
        )

    st.markdown(
        """
**Legal reality:** Assignment / offer PDFs are **operational templates**.
Have a Florida-licensed attorney and your title company review before live closings.
Title is your paymaster — disbursement language only works if they accept it.
        """
    )
