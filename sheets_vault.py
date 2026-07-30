"""
Google Sheets vault — persistent leads for 33615 War Room.
Falls back to local CRM SQLite if Sheets secrets are missing.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import pandas as pd

SHEET_COLUMNS = [
    "timestamp",
    "name",
    "address",
    "zip_code",
    "status",
    "arv",
    "mao",
    "fee",
    "buyer_name",
    "risk",
    "last_contacted",
]


def _ensure_secrets() -> None:
    try:
        from secrets_bootstrap import bootstrap_secrets

        bootstrap_secrets()
    except Exception:
        pass


def sheets_configured() -> bool:
    _ensure_secrets()
    url = (os.getenv("GOOGLE_SHEETS_URL") or "").strip()
    # Reject template URL so Go-Live does not show Sheets ON with placeholders
    if "YOUR_SHEET_ID" in url or "REAL_ID" in url:
        url = ""
    try:
        from secrets_bootstrap import is_placeholder_secret

        if is_placeholder_secret(url):
            url = ""
    except Exception:
        pass
    try:
        import streamlit as st

        secrets = getattr(st, "secrets", None)
        if secrets is not None:
            if "connections" in secrets and "gsheets" in secrets["connections"]:
                try:
                    g = secrets["connections"]["gsheets"]
                    sheet = g.get("spreadsheet") if hasattr(g, "get") else g["spreadsheet"]
                    sheet_s = str(sheet or "").strip()
                    if (
                        sheet_s
                        and "YOUR_SHEET_ID" not in sheet_s
                        and "REAL_ID" not in sheet_s
                    ):
                        return True
                except Exception:
                    pass
            try:
                su = secrets.get("GOOGLE_SHEETS_URL") if hasattr(secrets, "get") else None
            except Exception:
                su = None
            if su and "YOUR_SHEET_ID" not in str(su) and "REAL_ID" not in str(su):
                su_s = str(su).strip()
                if su_s:
                    return True
            if "gcp_service_account" in secrets:
                return bool(url or (su and "YOUR_SHEET_ID" not in str(su)))
    except Exception:
        pass
    return bool(url and os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"))


def sheets_missing_keys() -> list[str]:
    """Human-readable missing config names for Go-Live / Log Deal."""
    if sheets_configured():
        return []
    missing: list[str] = []
    url = (os.getenv("GOOGLE_SHEETS_URL") or "").strip()
    bad_url = (not url) or ("YOUR_SHEET_ID" in url) or ("REAL_ID" in url)
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
    if bad_url and not has_conn:
        missing.append("GOOGLE_SHEETS_URL")
        missing.append("[connections.gsheets].spreadsheet")
    if not has_sa and not os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"):
        missing.append("[gcp_service_account]")
    return missing


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=SHEET_COLUMNS)


def read_leads() -> pd.DataFrame:
    """Read Leads worksheet (or SQLite fallback)."""
    try:
        import streamlit as st
        from streamlit_gsheets import GSheetsConnection

        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Leads", ttl=0)
        if df is None or df.empty:
            return _empty_df()
        return df
    except Exception as exc:
        print(f"Sheets read fallback: {exc}")
        try:
            from crm import get_leads

            return get_leads()
        except Exception:
            return _empty_df()


def log_to_sheets(new_row: dict[str, Any]) -> tuple[bool, str]:
    """
    Append a deal row to Google Sheets 'Leads' tab.
    Returns (ok, message).
    """
    row = {c: new_row.get(c, "") for c in SHEET_COLUMNS}
    if not row.get("timestamp"):
        row["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not row.get("last_contacted"):
        row["last_contacted"] = row["timestamp"]

    # Always mirror to local CRM so follow-ups still work offline
    crm_ok = False
    try:
        from crm import add_lead

        add_lead(
            name=str(row.get("name") or "Seller"),
            address=str(row.get("address") or ""),
            status=str(row.get("status") or "Offered"),
            mao=float(row.get("mao") or 0),
            fee=float(row.get("fee") or 0),
            zip_code=str(row.get("zip_code") or ""),
            buyer_name=str(row.get("buyer_name") or ""),
        )
        crm_ok = True
    except Exception as exc:
        print(f"CRM mirror failed: {exc}")

    want_sheets = sheets_configured()
    if not want_sheets:
        # Local CRM mirror is fine; do not report success as if Google Vault wrote.
        if crm_ok:
            return (
                False,
                "Google Sheets Vault OFF — not logged to Sheets. "
                "Mirrored to local CRM only. Configure GOOGLE_SHEETS_URL / "
                "[connections.gsheets] + [gcp_service_account] for live Log Deal.",
            )
        return False, "Sheets not configured and local CRM save failed."

    try:
        import streamlit as st
        from streamlit_gsheets import GSheetsConnection

        conn = st.connection("gsheets", type=GSheetsConnection)
        existing = conn.read(worksheet="Leads", ttl=0)
        if existing is None or existing.empty:
            existing = _empty_df()
        updated = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
        conn.update(worksheet="Leads", data=updated)
        return True, "Deal locked in the Google Vault (+ local CRM mirror)."
    except Exception as exc:
        # Configured but failed — do not pretend Sheets wrote successfully.
        msg = f"Sheets configured but write failed: {exc}"
        if crm_ok:
            return False, f"{msg} (saved to local CRM only)."
        return False, msg
