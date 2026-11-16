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

# Primary acquisition CRM statuses (War Room)
CRM_STATUSES = (
    "Not Contacted",
    "Attempted",
    "Interested",
    "Negotiating",
    "Follow Up",
    "Under Contract",
    "Closed",
    "Do Not Contact",
)

# Legacy statuses kept so existing leads still validate
_LEGACY_STATUSES = (
    "New Lead",
    "Offer Sent",
    "Hot Lead",
    "Lis Pendens",
    "Follow-up Sent",
    "Dead",
    "SIGNED",
)

STATUSES = CRM_STATUSES + tuple(s for s in _LEGACY_STATUSES if s not in CRM_STATUSES)

INACTIVE_STATUSES = ("Closed", "Do Not Contact", "Dead", "SIGNED")

QUEUE_STATUSES = ("QUEUED", "SENT", "FAILED", "SKIPPED")

CALL_OUTCOMES = (
    "initiated",
    "answered",
    "missed",
    "failed",
    "busy",
    "voicemail",
    "completed",
)


def is_do_not_contact(lead: dict[str, Any]) -> bool:
    """True for both migrated DNC flags and legacy DNC status-only rows."""
    status = str(lead.get("status") or "").strip().lower()
    return bool(lead.get("dnc_flag")) or status == "do not contact"


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
        "seller_email": "TEXT DEFAULT ''",
        "last_contacted": "TEXT DEFAULT ''",
        "wholesale_fee": "REAL DEFAULT 10000",
        "risk_level": "TEXT DEFAULT 'Standard'",
        # Zombie / assignment blueprint fields
        "mailing_address": "TEXT DEFAULT ''",
        "vacant": "INTEGER DEFAULT 0",
        "absentee": "INTEGER DEFAULT 0",
        "owner_occupied": "INTEGER DEFAULT -1",
        "code_violation": "INTEGER DEFAULT 0",
        "tax_delinquent": "INTEGER DEFAULT 0",
        "foreclosure_case": "TEXT DEFAULT ''",
        "lender": "TEXT DEFAULT ''",
        "unpaid_taxes": "REAL DEFAULT 0",
        "municipal_liens": "REAL DEFAULT 0",
        "hoa_dues": "REAL DEFAULT 0",
        "probate": "INTEGER DEFAULT 0",
        "estimated_equity": "REAL DEFAULT 0",
        "last_sale_price": "REAL DEFAULT 0",
        "repairs_estimate": "REAL DEFAULT 0",
        "owner_contact_status": "TEXT DEFAULT 'Unknown'",
        "motivation_score": "INTEGER DEFAULT 0",
        "motivation_tier": "TEXT DEFAULT ''",
        "motive_tags": "TEXT DEFAULT ''",
        "title_status": "TEXT DEFAULT 'Not Sent'",
        "buyer_status": "TEXT DEFAULT 'None'",
        "notes": "TEXT DEFAULT ''",
        "phone_source": "TEXT DEFAULT ''",
        "phone_confidence": "TEXT DEFAULT ''",
        "callback_at": "TEXT DEFAULT ''",
        "dnc_flag": "INTEGER DEFAULT 0",
        "contact_permission": "TEXT DEFAULT ''",
    }
    for name, decl in extras.items():
        if name not in cols:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {name} {decl}")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS call_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            address TEXT DEFAULT '',
            agent_phone TEXT DEFAULT '',
            lead_phone TEXT DEFAULT '',
            mode TEXT DEFAULT '',
            status TEXT DEFAULT '',
            agent_sid TEXT DEFAULT '',
            lead_sid TEXT DEFAULT '',
            duration_sec INTEGER DEFAULT 0,
            error TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            ai_summary TEXT DEFAULT '',
            is_test INTEGER DEFAULT 0,
            created_at TEXT DEFAULT ''
        )
        """
    )
    call_cols = {row[1] for row in conn.execute("PRAGMA table_info(call_logs)").fetchall()}
    if "ai_summary" not in call_cols:
        conn.execute("ALTER TABLE call_logs ADD COLUMN ai_summary TEXT DEFAULT ''")


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
    seller_email: str = "",
    mailing_address: str = "",
    vacant: bool = False,
    absentee: bool = False,
    owner_occupied: bool | None = None,
    code_violation: bool = False,
    tax_delinquent: bool = False,
    foreclosure_case: str = "",
    lender: str = "",
    unpaid_taxes: float = 0.0,
    municipal_liens: float = 0.0,
    hoa_dues: float = 0.0,
    probate: bool = False,
    estimated_equity: float = 0.0,
    last_sale_price: float = 0.0,
    repairs_estimate: float = 0.0,
    owner_contact_status: str = "Unknown",
    motivation_score: int = 0,
    motivation_tier: str = "",
    motive_tags: str = "",
    title_status: str = "Not Sent",
    buyer_status: str = "None",
    notes: str = "",
) -> int:
    """Insert a Tampa lead. Returns new row id."""
    init_db()
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if owner_occupied is True:
        oo = 1
    elif owner_occupied is False:
        oo = 0
    else:
        oo = -1
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO leads (
                address, zip_code, arv, mao, wholesale_fee, risk_level,
                flood_risk, status, seller_name, seller_phone, seller_email,
                mailing_address, vacant, absentee, owner_occupied,
                code_violation, tax_delinquent, foreclosure_case, lender,
                unpaid_taxes, municipal_liens, hoa_dues, probate,
                estimated_equity, last_sale_price, repairs_estimate,
                owner_contact_status, motivation_score, motivation_tier,
                motive_tags, title_status, buyer_status, notes, date_added
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
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
                seller_email,
                mailing_address,
                1 if vacant else 0,
                1 if absentee else 0,
                oo,
                1 if code_violation else 0,
                1 if tax_delinquent else 0,
                (foreclosure_case or "").strip(),
                (lender or "").strip(),
                float(unpaid_taxes or 0),
                float(municipal_liens or 0),
                float(hoa_dues or 0),
                1 if probate else 0,
                float(estimated_equity or 0),
                float(last_sale_price or 0),
                float(repairs_estimate or 0),
                owner_contact_status or "Unknown",
                int(motivation_score or 0),
                motivation_tier or "",
                motive_tags or "",
                title_status or "Not Sent",
                buyer_status or "None",
                notes or "",
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


def update_lead_contact(
    lead_id: int,
    *,
    phone: str = "",
    email: str = "",
    seller_name: str = "",
    mailing_address: str = "",
    phone_source: str = "",
    phone_confidence: str = "",
    owner_contact_status: str = "",
) -> bool:
    """Persist skip-trace / paste contact fields. Empty strings leave existing values."""
    init_db()
    lead = get_lead(lead_id)
    if not lead:
        return False
    phone_v = (phone or "").strip() or (lead.get("seller_phone") or "")
    email_v = (email or "").strip() or (lead.get("seller_email") or "")
    name_v = (seller_name or "").strip() or (lead.get("seller_name") or "")
    mail_v = (mailing_address or "").strip() or (lead.get("mailing_address") or "")
    src_v = (phone_source or "").strip() or (lead.get("phone_source") or "")
    conf_v = (phone_confidence or "").strip() or (lead.get("phone_confidence") or "")
    ocs = (owner_contact_status or "").strip()
    if not ocs:
        if phone_v:
            ocs = "Phone Found"
        elif email_v:
            ocs = "Email Found"
        else:
            ocs = lead.get("owner_contact_status") or "Unknown"
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE leads SET
                seller_phone = ?,
                seller_email = ?,
                seller_name = ?,
                mailing_address = ?,
                phone_source = ?,
                phone_confidence = ?,
                owner_contact_status = ?
            WHERE id = ?
            """,
            (phone_v, email_v, name_v, mail_v, src_v, conf_v, ocs, lead_id),
        )
        conn.commit()
        return cur.rowcount > 0


def set_lead_callback(lead_id: int, callback_at: str, notes: str = "") -> bool:
    init_db()
    with _connect() as conn:
        if notes.strip():
            cur = conn.execute(
                """
                UPDATE leads SET callback_at = ?,
                    notes = TRIM(COALESCE(notes,'') || ' ' || ?)
                WHERE id = ?
                """,
                ((callback_at or "").strip(), notes.strip(), lead_id),
            )
        else:
            cur = conn.execute(
                "UPDATE leads SET callback_at = ? WHERE id = ?",
                ((callback_at or "").strip(), lead_id),
            )
        conn.commit()
        return cur.rowcount > 0


def set_lead_dnc(lead_id: int, flagged: bool = True) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE leads SET dnc_flag = ?, owner_contact_status = CASE WHEN ? THEN 'Do Not Contact' ELSE owner_contact_status END WHERE id = ?",
            (1 if flagged else 0, 1 if flagged else 0, lead_id),
        )
        conn.commit()
        return cur.rowcount > 0


def recent_call_exists(lead_phone: str, *, within_seconds: int = 120) -> bool:
    """Prevent duplicate outbound dials to the same number within a short window."""
    init_db()
    phone = (lead_phone or "").strip()
    if not phone:
        return False
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT created_at FROM call_logs
            WHERE lead_phone = ? AND status IN ('queued', 'ringing', 'in-progress', 'ok', 'initiated')
            ORDER BY id DESC LIMIT 1
            """,
            (phone,),
        ).fetchone()
    if not row:
        return False
    try:
        then = datetime.strptime(str(row["created_at"]), "%Y-%m-%d %H:%M:%S")
        return (datetime.now() - then).total_seconds() < within_seconds
    except Exception:
        return False


def log_call(
    *,
    lead_id: int | None,
    address: str = "",
    agent_phone: str = "",
    lead_phone: str = "",
    mode: str = "",
    status: str = "",
    agent_sid: str = "",
    lead_sid: str = "",
    duration_sec: int = 0,
    error: str = "",
    notes: str = "",
    is_test: bool = False,
) -> int:
    init_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO call_logs (
                lead_id, address, agent_phone, lead_phone, mode, status,
                agent_sid, lead_sid, duration_sec, error, notes, is_test, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lead_id,
                address or "",
                agent_phone or "",
                lead_phone or "",
                mode or "",
                status or "",
                agent_sid or "",
                lead_sid or "",
                int(duration_sec or 0),
                error or "",
                notes or "",
                1 if is_test else 0,
                now,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_call_logs(lead_id: int | None = None, *, limit: int = 25) -> list[dict[str, Any]]:
    init_db()
    limit = max(1, min(int(limit), 100))
    with _connect() as conn:
        if lead_id is not None:
            rows = conn.execute(
                "SELECT * FROM call_logs WHERE lead_id = ? ORDER BY id DESC LIMIT ?",
                (int(lead_id), limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM call_logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


def update_call_log(
    call_id: int,
    *,
    status: str = "",
    duration_sec: int | None = None,
    notes: str = "",
    error: str = "",
    ai_summary: str = "",
) -> bool:
    init_db()
    with _connect() as conn:
        row = conn.execute("SELECT * FROM call_logs WHERE id = ?", (call_id,)).fetchone()
        if not row:
            return False
        cur = conn.execute(
            """
            UPDATE call_logs SET
                status = COALESCE(NULLIF(?, ''), status),
                duration_sec = COALESCE(?, duration_sec),
                notes = CASE WHEN ? != '' THEN ? ELSE notes END,
                error = CASE WHEN ? != '' THEN ? ELSE error END,
                ai_summary = CASE WHEN ? != '' THEN ? ELSE ai_summary END
            WHERE id = ?
            """,
            (
                (status or "").strip(),
                duration_sec,
                (notes or "").strip(),
                (notes or "").strip(),
                (error or "").strip(),
                (error or "").strip(),
                (ai_summary or "").strip(),
                (ai_summary or "").strip(),
                call_id,
            ),
        )
        conn.commit()
        return cur.rowcount > 0


def append_lead_note(lead_id: int, note: str) -> bool:
    """Append a timestamped seller note. Does not dial or message anyone."""
    text = (note or "").strip()
    if not text:
        return False
    init_db()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"[{stamp}] {text}"
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE leads SET notes = TRIM(
                CASE
                    WHEN COALESCE(notes, '') = '' THEN ?
                    ELSE notes || char(10) || ?
                END
            )
            WHERE id = ?
            """,
            (line, line, lead_id),
        )
        conn.commit()
        return cur.rowcount > 0


def ai_summary_stub(*, transcript: str = "", call_id: int | None = None) -> str:
    """
    Placeholder for future authorized transcription + AI summary.
    Does not call any LLM and does not invent content from audio.
    """
    if not (transcript or "").strip():
        return (
            "[AI summary pending] Enable authorized recording/transcription, "
            "then store the transcript to generate a summary. No audio processed."
        )
    preview = " ".join((transcript or "").split())[:240]
    return f"[AI summary stub — not generated] Transcript on file ({len(transcript)} chars): {preview}"


def get_callbacks_due(*, now: datetime | None = None) -> list[dict[str, Any]]:
    """Active leads with callback_at set (overdue + upcoming)."""
    init_db()
    now = now or datetime.now()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM leads
            WHERE COALESCE(callback_at, '') != ''
              AND status NOT IN ('Closed', 'Do Not Contact', 'Dead', 'SIGNED')
            ORDER BY callback_at ASC
            """
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        raw = str(item.get("callback_at") or "").strip()
        overdue = False
        upcoming = False
        try:
            # Accept "YYYY-MM-DD" or "YYYY-MM-DD HH:MM"
            if len(raw) <= 10:
                when = datetime.strptime(raw[:10], "%Y-%m-%d")
            else:
                try:
                    when = datetime.strptime(raw[:16], "%Y-%m-%d %H:%M")
                except ValueError:
                    when = datetime.strptime(raw[:10], "%Y-%m-%d")
            overdue = when <= now
            upcoming = (not overdue) and (when - now).total_seconds() <= 48 * 3600
        except Exception:
            overdue = False
            upcoming = False
        item["callback_overdue"] = overdue
        item["callback_upcoming"] = upcoming
        out.append(item)
    return out


def daily_call_dashboard(*, day: str | None = None) -> dict[str, Any]:
    """
    Calls made today, answered, failed, callbacks due, interested sellers.
    day: YYYY-MM-DD (defaults to today local).
    """
    init_db()
    day = day or datetime.now().strftime("%Y-%m-%d")
    with _connect() as conn:
        calls = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM call_logs WHERE substr(created_at, 1, 10) = ? ORDER BY id DESC",
                (day,),
            ).fetchall()
        ]
        interested = [
            dict(r)
            for r in conn.execute(
                """
                SELECT * FROM leads
                WHERE status IN ('Interested', 'Negotiating', 'Follow Up', 'Hot Lead')
                  AND status NOT IN ('Closed', 'Do Not Contact', 'Dead', 'SIGNED')
                ORDER BY date_added DESC
                """
            ).fetchall()
        ]
    answered = sum(
        1
        for c in calls
        if str(c.get("status") or "").lower() in {"answered", "completed", "ok"}
    )
    failed = sum(
        1
        for c in calls
        if str(c.get("status") or "").lower() in {"failed", "missed", "busy"}
        or (c.get("error") or "").strip()
    )
    callbacks = get_callbacks_due()
    overdue = [c for c in callbacks if c.get("callback_overdue")]
    upcoming = [c for c in callbacks if c.get("callback_upcoming")]
    return {
        "day": day,
        "calls_made": len(calls),
        "answered": answered,
        "failed": failed,
        "calls": calls,
        "callbacks_due": overdue,
        "callbacks_upcoming": upcoming,
        "interested": interested,
    }


def address_already_active(address: str) -> bool:
    """True if a non-Dead/Closed lead already exists for this address."""
    init_db()
    key = " ".join((address or "").lower().split())
    if not key:
        return False
    with _connect() as conn:
        rows = conn.execute(
            "SELECT address FROM leads WHERE status NOT IN ('Dead', 'Closed', 'SIGNED', 'Do Not Contact')"
        ).fetchall()
    for row in rows:
        if " ".join(str(row["address"] or "").lower().split()) == key:
            return True
    return False


def mark_institutional_leads_dead() -> int:
    """Mark LLC/SFR/trust-style owners Dead so they leave the active pipeline."""
    from seller_factory import is_institutional_owner

    init_db()
    killed = 0
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, seller_name, status FROM leads WHERE status NOT IN ('Dead', 'Closed', 'SIGNED', 'Do Not Contact')"
        ).fetchall()
        for row in rows:
            if is_institutional_owner(str(row["seller_name"] or "")):
                conn.execute(
                    "UPDATE leads SET status = 'Dead', notes = COALESCE(notes,'') || ' [auto: institutional owner]' WHERE id = ?",
                    (int(row["id"]),),
                )
                killed += 1
        conn.commit()
    return killed


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
            WHERE status NOT IN ('Closed', 'Dead', 'SIGNED', 'Do Not Contact')
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
