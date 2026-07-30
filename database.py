"""
Tampa War Room — portfolio lead storage (tampa_leads.db).
Separate from deals.db (click-to-sign contracts).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "tampa_leads.db"

STATUSES = (
    "New Lead",
    "Offer Sent",
    "Hot Lead",
    "Lis Pendens",
    "Follow-up Sent",
    "Dead",
    "Closed",
    "SIGNED",
)

QUEUE_STATUSES = ("QUEUED", "SENT", "FAILED", "SKIPPED")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT,
                zip_code TEXT,
                arv REAL,
                mao REAL,
                wholesale_fee REAL,
                risk_level TEXT,
                flood_risk INTEGER DEFAULT 0,
                status TEXT DEFAULT 'New Lead',
                seller_name TEXT DEFAULT '',
                seller_phone TEXT DEFAULT '',
                last_contacted TEXT DEFAULT '',
                date_added TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS offer_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                deal_id TEXT DEFAULT '',
                address TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                seller_name TEXT DEFAULT '',
                offer_price REAL DEFAULT 0,
                pdf_path TEXT DEFAULT '',
                sms_preview TEXT DEFAULT '',
                status TEXT DEFAULT 'QUEUED',
                error TEXT DEFAULT '',
                created_at TEXT DEFAULT '',
                sent_at TEXT DEFAULT ''
            )
            """
        )
        _migrate(conn)
        conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(leads)").fetchall()}
    extras = {
        "flood_risk": "INTEGER DEFAULT 0",
        "seller_name": "TEXT DEFAULT ''",
        "seller_phone": "TEXT DEFAULT ''",
        "last_contacted": "TEXT DEFAULT ''",
        "wholesale_fee": "REAL DEFAULT 10000",
        "risk_level": "TEXT DEFAULT 'Standard'",
    }
    for name, decl in extras.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {name} {decl}")


def save_lead(
    address: str,
    zip_code: str,
    arv: float,
    mao: float,
    fee: float,
    risk: str,
    *,
    flood_risk: bool = False,
    status: str = "New Lead",
    seller_name: str = "",
    seller_phone: str = "",
) -> int:
    """Insert a Tampa lead. Returns new row id."""
    init_db()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO leads (
                address, zip_code, arv, mao, wholesale_fee, risk_level,
                flood_risk, status, seller_name, seller_phone, date_added
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                address,
                zip_code,
                float(arv),
                float(mao),
                float(fee),
                risk,
                1 if flood_risk else 0,
                status if status in STATUSES else "New Lead",
                seller_name,
                seller_phone,
                date,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_all_leads() -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM leads ORDER BY date_added DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_lead(lead_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    return dict(row) if row else None


def update_lead_phone(lead_id: int, phone: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE leads SET seller_phone = ? WHERE id = ?",
            ((phone or "").strip(), lead_id),
        )
        conn.commit()
        return cur.rowcount > 0


def update_lead_status(lead_id: int, status: str) -> bool:
    if status not in STATUSES:
        return False
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE leads SET status = ? WHERE id = ?",
            (status, lead_id),
        )
        conn.commit()
        return cur.rowcount > 0


def mark_contacted(lead_id: int, status: str | None = None) -> bool:
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        if status and status in STATUSES:
            cur = conn.execute(
                "UPDATE leads SET last_contacted = ?, status = ? WHERE id = ?",
                (now, status, lead_id),
            )
        else:
            cur = conn.execute(
                "UPDATE leads SET last_contacted = ? WHERE id = ?",
                (now, lead_id),
            )
        conn.commit()
        return cur.rowcount > 0


def pipeline_stats(leads: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Total ARV, potential profit, zip density."""
    rows = leads if leads is not None else get_all_leads()
    zip_counts: dict[str, int] = {}
    for r in rows:
        z = (r.get("zip_code") or "?????")[:5]
        zip_counts[z] = zip_counts.get(z, 0) + 1
    hottest = sorted(zip_counts.items(), key=lambda x: x[1], reverse=True)
    return {
        "count": len(rows),
        "pipeline_arv": sum(float(r.get("arv") or 0) for r in rows),
        "potential_profit": sum(float(r.get("wholesale_fee") or 0) for r in rows),
        "zip_density": hottest,
        "hottest_zip": hottest[0][0] if hottest else "—",
        "hottest_count": hottest[0][1] if hottest else 0,
    }


def get_pending_leads() -> list[dict[str, Any]]:
    """
    Leads eligible for bulk follow-up: not Closed/Dead, preferably with a phone.
    """
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM leads
            WHERE status NOT IN ('Closed', 'Dead', 'SIGNED')
            ORDER BY date_added DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_agent_candidate_leads(
    *,
    zip_code: str = "",
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    New Leads not already QUEUED/SENT in offer_queue — ready for Contract Agent.
    """
    init_db()
    zip_code = (zip_code or "").strip()[:5]
    limit = max(1, min(int(limit), 50))
    with _connect() as conn:
        if zip_code:
            rows = conn.execute(
                """
                SELECT l.* FROM leads l
                WHERE l.status = 'New Lead'
                  AND substr(COALESCE(l.zip_code, ''), 1, 5) = ?
                  AND l.id NOT IN (
                    SELECT lead_id FROM offer_queue
                    WHERE status IN ('QUEUED', 'SENT') AND lead_id IS NOT NULL
                  )
                ORDER BY l.date_added DESC
                LIMIT ?
                """,
                (zip_code, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT l.* FROM leads l
                WHERE l.status = 'New Lead'
                  AND l.id NOT IN (
                    SELECT lead_id FROM offer_queue
                    WHERE status IN ('QUEUED', 'SENT') AND lead_id IS NOT NULL
                  )
                ORDER BY l.date_added DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def enqueue_offer(
    *,
    lead_id: int | None,
    deal_id: str,
    address: str,
    phone: str,
    seller_name: str,
    offer_price: float,
    pdf_path: str,
    sms_preview: str,
    status: str = "QUEUED",
    error: str = "",
) -> int:
    init_db()
    if status not in QUEUE_STATUSES:
        status = "QUEUED"
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO offer_queue (
                lead_id, deal_id, address, phone, seller_name, offer_price,
                pdf_path, sms_preview, status, error, created_at, sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead_id,
                deal_id or "",
                address or "",
                phone or "",
                seller_name or "",
                float(offer_price or 0),
                pdf_path or "",
                sms_preview or "",
                status,
                error or "",
                now,
                now if status == "SENT" else "",
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_offer_queue_item(queue_id: int) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM offer_queue WHERE id = ?", (queue_id,)
        ).fetchone()
    return dict(row) if row else None


def list_queued_offers(status: str = "QUEUED") -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT * FROM offer_queue
                WHERE status = ?
                ORDER BY created_at DESC
                """,
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM offer_queue ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def mark_offer_sent(queue_id: int) -> bool:
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE offer_queue
            SET status = 'SENT', sent_at = ?, error = ''
            WHERE id = ?
            """,
            (now, queue_id),
        )
        conn.commit()
        return cur.rowcount > 0


def mark_offer_failed(queue_id: int, error: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE offer_queue
            SET status = 'FAILED', error = ?
            WHERE id = ?
            """,
            ((error or "").strip(), queue_id),
        )
        conn.commit()
        return cur.rowcount > 0


def find_offer_by_deal_id(deal_id: str) -> dict[str, Any] | None:
    init_db()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM offer_queue
            WHERE deal_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            ((deal_id or "").strip(),),
        ).fetchone()
    return dict(row) if row else None


def set_lead_signed_for_deal(deal_id: str) -> bool:
    """
    When a deal is signed, flip the linked War Room lead to SIGNED.
    Looks up lead_id from offer_queue, or from deals.lead_id via db.get_deal.
    """
    deal_id = (deal_id or "").strip()
    if not deal_id:
        return False

    lead_id: int | None = None
    queued = find_offer_by_deal_id(deal_id)
    if queued and queued.get("lead_id") is not None:
        try:
            lead_id = int(queued["lead_id"])
        except (TypeError, ValueError):
            lead_id = None

    if lead_id is None:
        try:
            from db import get_deal

            deal = get_deal(deal_id)
            if deal and deal.get("lead_id") not in (None, "", 0, "0"):
                lead_id = int(deal["lead_id"])
        except Exception:
            lead_id = None

    if lead_id is None:
        return False
    return update_lead_status(lead_id, "SIGNED")
