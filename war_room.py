"""
Tampa War Room Streamlit panel — portfolio, stats, bulk + single follow-up SMS.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from comms import send_followup_sms
from database import (
    STATUSES,
    get_all_leads,
    get_pending_leads,
    mark_contacted,
    pipeline_stats,
    update_lead_status,
)


def _style_war_room(df: pd.DataFrame):
    def row_style(row: pd.Series) -> list[str]:
        status = str(row.get("Status", ""))
        flood = bool(row.get("Flood", False))
        if flood or "Flood" in str(row.get("Risk", "")):
            color = "background-color: #5c1a1a; color: #ffb4b4"
        elif status == "Offer Sent":
            color = "background-color: #1a3d2a; color: #b6f5c8"
        elif status in {"Hot Lead", "New Lead"}:
            color = "background-color: #3d3200; color: #ffe566"
        elif status == "Lis Pendens":
            color = "background-color: #3d1a4d; color: #e0b3ff"
        else:
            color = ""
        return [color] * len(row)

    return df.style.apply(row_style, axis=1)


def render_war_room(buyer_name: str = "DealShark") -> None:
    st.title("Tampa War Room")
    st.caption("Every Tampa lead · flood risk · offer status · bulk follow-up. Open at 9 AM.")

    leads = get_all_leads()
    stats = pipeline_stats(leads)

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Leads", f"{stats['count']}")
    s2.metric("Total Pipeline Value (ARV)", f"${stats['pipeline_arv']:,.0f}")
    s3.metric("Potential Profit (Fees)", f"${stats['potential_profit']:,.0f}")
    s4.metric(
        "Hillsborough Density",
        f"{stats['hottest_zip']} ({stats['hottest_count']})",
    )

    if stats["zip_density"]:
        dens = ", ".join(f"{z}:{n}" for z, n in stats["zip_density"][:5])
        st.caption(f"Zip heat map: {dens}")

    st.markdown("---")
    st.subheader("Bulk Follow-up Hammer")
    st.caption(
        "Texts every non-Closed/Dead lead that has a phone number. "
        "Lis Pendens status uses the stop-auction script."
    )
    dry_run = st.checkbox("Dry run (don't send — just preview)", value=True)
    if st.button("Launch Bulk Follow-up", type="primary"):
        pending = get_pending_leads()
        with_phone = [p for p in pending if (p.get("seller_phone") or "").strip()]
        without = len(pending) - len(with_phone)
        if not pending:
            st.warning("No pending leads to follow up with.")
        elif not with_phone:
            st.warning(
                f"{len(pending)} pending lead(s) but none have phone numbers. "
                "Save leads with Twilio Mobile # from the Calculator."
            )
        else:
            sent = 0
            failed = 0
            for lead in with_phone:
                address = lead.get("address") or ""
                mao = float(lead.get("mao") or 0)
                phone = (lead.get("seller_phone") or "").strip()
                status = lead.get("status") or "New Lead"
                if dry_run:
                    st.info(
                        f"[DRY RUN] Would text {phone} · {address} · ${mao:,.0f} · {status}"
                    )
                    continue
                sid = send_followup_sms(
                    phone,
                    address,
                    seller_name=lead.get("seller_name") or "",
                    buyer_name=buyer_name,
                    mao=mao,
                    status=status,
                    zip_code=str(lead.get("zip_code") or ""),
                )
                if sid:
                    mark_contacted(int(lead["id"]), status="Follow-up Sent")
                    st.success(f"Sent follow-up for: {address}")
                    sent += 1
                else:
                    st.error(f"Failed: {address}")
                    failed += 1
            if dry_run:
                st.warning(
                    f"Dry run complete · {len(with_phone)} would send · "
                    f"{without} skipped (no phone). Uncheck Dry run to fire for real."
                )
            else:
                st.balloons()
                st.success(f"Bulk done · sent {sent} · failed {failed} · no-phone {without}")

    if not leads:
        st.info(
            "No leads yet. Calculator → **Save Lead to War Room** "
            "(or Generate PDF / Fire SMS)."
        )
        return

    rows = []
    for r in leads:
        rows.append(
            {
                "ID": r["id"],
                "Address": r.get("address") or "",
                "Zip": r.get("zip_code") or "",
                "ARV": float(r.get("arv") or 0),
                "MAO": float(r.get("mao") or 0),
                "Fee": float(r.get("wholesale_fee") or 0),
                "Risk": r.get("risk_level") or "Standard",
                "Flood": bool(r.get("flood_risk")),
                "Status": r.get("status") or "New Lead",
                "Phone": r.get("seller_phone") or "",
                "Last Contact": r.get("last_contacted") or "—",
                "Date": r.get("date_added") or "",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(_style_war_room(df), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Lead Actions")
    for r in leads:
        flood_tag = " · FLOOD" if r.get("flood_risk") else ""
        label = (
            f"#{r['id']} · {r.get('status')} · {r.get('address')} · "
            f"MAO ${float(r.get('mao') or 0):,.0f}{flood_tag}"
        )
        with st.expander(label, expanded=False):
            c1, c2, c3 = st.columns(3)
            with c1:
                new_status = st.selectbox(
                    "Status",
                    list(STATUSES),
                    index=list(STATUSES).index(r["status"])
                    if r.get("status") in STATUSES
                    else 0,
                    key=f"wr_status_{r['id']}",
                )
                if st.button("Update Status", key=f"wr_upd_{r['id']}"):
                    update_lead_status(int(r["id"]), new_status)
                    st.toast(f"#{r['id']} → {new_status}")
                    st.rerun()
            with c2:
                st.write(f"**Phone:** {r.get('seller_phone') or '—'}")
                st.write(f"**Seller:** {r.get('seller_name') or '—'}")
                st.write(f"**Risk:** {r.get('risk_level')}")
            with c3:
                if st.button("Send Follow-up SMS", key=f"wr_sms_{r['id']}", type="primary"):
                    phone = (r.get("seller_phone") or "").strip()
                    if not phone:
                        st.error("No phone on this lead.")
                    else:
                        sid = send_followup_sms(
                            phone,
                            r.get("address") or "",
                            seller_name=r.get("seller_name") or "",
                            buyer_name=buyer_name,
                            mao=float(r.get("mao") or 0),
                            status=new_status or r.get("status") or "",
                            zip_code=str(r.get("zip_code") or ""),
                        )
                        if sid:
                            mark_contacted(
                                int(r["id"]),
                                status="Follow-up Sent"
                                if new_status != "Lis Pendens"
                                else "Lis Pendens",
                            )
                            st.success(f"Follow-up sent. SID: `{sid}`")
                            st.rerun()
                        else:
                            st.error("SMS failed — check Twilio `.env` keys.")
