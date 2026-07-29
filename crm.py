"""
CRM ledger — Offered / Under Contract / Closed + 72h follow-up tracking.
Uses crm.db (not deals.db — that holds click-to-sign contracts).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

DB_PATH = Path(__file__).resolve().parent / "crm.db"

STATUSES = ("New", "Offered", "Under Contract", "Closed", "Dead")


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                address TEXT,
                status TEXT,
                mao REAL,
                fee REAL,
                zip_code TEXT DEFAULT '',
                buyer_name TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_contacted TEXT DEFAULT ''
            )
            """
        )
        cols = {row[1] for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
        if "last_contacted" not in cols:
            conn.execute("ALTER TABLE leads ADD COLUMN last_contacted TEXT DEFAULT ''")
        conn.commit()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def add_lead(
    name: str,
    address: str,
    status: str,
    mao: float,
    fee: float,
    *,
    zip_code: str = "",
    buyer_name: str = "",
) -> int:
    init_db()
    status = status if status in STATUSES else "Offered"
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO leads (
                name, address, status, mao, fee, zip_code, buyer_name,
                created_at, last_contacted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, address, status, float(mao), float(fee), zip_code, buyer_name, now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_leads() -> pd.DataFrame:
    init_db()
    with _connect() as conn:
        return pd.read_sql_query("SELECT * FROM leads ORDER BY id DESC", conn)


def update_contact_date(address: str) -> bool:
    """Bump last_contacted to NOW for a lead address."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE leads SET last_contacted = ? WHERE address = ?",
            (_now(), address),
        )
        conn.commit()
        return cur.rowcount > 0


def update_contact_date_by_id(lead_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE leads SET last_contacted = ? WHERE id = ?",
            (_now(), lead_id),
        )
        conn.commit()
        return cur.rowcount > 0


def get_stale_leads(hours: int = 72) -> pd.DataFrame:
    """
    Leads not contacted within `hours` (default 72) and not Closed/Dead.
    Also includes blank last_contacted rows older than created_at window.
    """
    init_db()
    # SQLite datetime compare works with ISO-ish 'YYYY-MM-DD HH:MM:SS'
    query = f"""
        SELECT * FROM leads
        WHERE status NOT IN ('Closed', 'Dead')
          AND (
            last_contacted IS NULL
            OR last_contacted = ''
            OR datetime(last_contacted) < datetime('now', '-{int(hours)} hours')
          )
        ORDER BY last_contacted ASC, id ASC
    """
    with _connect() as conn:
        return pd.read_sql_query(query, conn)


def pending_assignment_fees() -> float:
    df = get_leads()
    if df.empty:
        return 0.0
    under = df[df["status"] == "Under Contract"]
    return float(under["fee"].sum()) if not under.empty else 0.0


def pipeline_snapshot() -> dict[str, Any]:
    df = get_leads()
    stale = get_stale_leads(72)
    if df.empty:
        return {
            "count": 0,
            "under_contract_fees": 0.0,
            "offered_fees": 0.0,
            "recent": [],
            "stale_count": 0,
        }
    return {
        "count": len(df),
        "under_contract_fees": float(df[df["status"] == "Under Contract"]["fee"].sum()),
        "offered_fees": float(df[df["status"] == "Offered"]["fee"].sum()),
        "recent": df.head(5).to_dict("records"),
        "stale_count": len(stale),
    }
