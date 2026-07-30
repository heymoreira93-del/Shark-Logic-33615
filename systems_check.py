"""
Stack health — Twilio / Stripe / Sheets / Email / RentCast / People-data.
Surfaces what's live vs what's blocking money today.
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _has(key: str) -> bool:
    val = (os.getenv(key) or "").strip()
    return bool(val) and val not in {
        "your_key_here",
        "your_sid",
        "your_token",
        "your_rentcast_key",
        "sk_test_...",
        "your_gmail_app_password",
    }


def twilio_status() -> dict[str, Any]:
    sid = _has("TWILIO_ACCOUNT_SID")
    token = _has("TWILIO_AUTH_TOKEN")
    from_n = (os.getenv("TWILIO_PHONE_NUMBER") or "").strip()
    ok_from = bool(from_n) and from_n.startswith("+") and not from_n.startswith("++")
    ready = sid and token and ok_from
    notes = []
    if not sid or not token:
        notes.append("Missing TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN")
    if not ok_from:
        notes.append("TWILIO_PHONE_NUMBER must be E.164 like +1888...")
    notes.append(
        "Trial accounts can ONLY text verified numbers in Twilio Console → Verified Caller IDs."
    )
    notes.append("Upgrade Twilio to send to any US cell.")
    return {"ready": ready, "label": "Twilio SMS", "notes": notes}


def stripe_status() -> dict[str, Any]:
    ready = _has("STRIPE_SECRET_KEY") and _has("APP_BASE_URL")
    notes = []
    if not _has("STRIPE_SECRET_KEY"):
        notes.append("Missing STRIPE_SECRET_KEY in Cloud Secrets")
    if not _has("APP_BASE_URL"):
        notes.append("Missing APP_BASE_URL (no trailing slash)")
    else:
        notes.append(f"APP_BASE_URL={os.getenv('APP_BASE_URL', '').rstrip('/')}")
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
        and bool((os.getenv("BUYER_EMAILS") or "").strip())
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
    st.markdown(
        """
**Legal reality:** Assignment / offer PDFs are **operational templates**.
Have a Florida real-estate attorney and your title company review before live closings.
Title is your paymaster — disbursement language only works if they accept it.
        """
    )
