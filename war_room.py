"""
Tampa War Room Streamlit panel — portfolio, stats, Contract Agent, offer queue, SMS.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from comms import send_followup_sms, send_queued_offer
from contract_agent import run_contract_agent
from database import (
    STATUSES,
    get_all_leads,
    get_pending_leads,
    list_queued_offers,
    mark_contacted,
    pipeline_stats,
    update_lead_phone,
    update_lead_status,
)
from phone_enrich import people_data_configured
from tampa_config import MIN_WHOLESALE_FEE
from voice import agent_phone, click_to_call, voice_configured


def _style_war_room(df: pd.DataFrame):
    """Color rows when Jinja2 is available; otherwise return plain DataFrame."""
    def row_style(row: pd.Series) -> list[str]:
        status = str(row.get("Status", ""))
        flood = bool(row.get("Flood", False))
        if flood or "Flood" in str(row.get("Risk", "")):
            color = "background-color: #5c1a1a; color: #ffb4b4"
        elif status == "SIGNED":
            color = "background-color: #0d3b66; color: #b8e1ff"
        elif status == "Offer Sent":
            color = "background-color: #1a3d2a; color: #b6f5c8"
        elif status in {"Hot Lead", "New Lead"}:
            color = "background-color: #3d3200; color: #ffe566"
        elif status == "Lis Pendens":
            color = "background-color: #3d1a4d; color: #e0b3ff"
        else:
            color = ""
        return [color] * len(row)

    try:
        return df.style.apply(row_style, axis=1)
    except (AttributeError, ImportError):
        return df


def _render_contract_agent(buyer_name: str) -> None:
    st.subheader("Contract Agent")
    st.caption(
        "Hunt → phone (paste or People Data) → MAO → cash-offer PDF → signing link → "
        "**queue only**. You review and tap Send. No auto-SMS."
    )

    people_on = people_data_configured()
    if people_on:
        st.success("People-Data ON — agent can auto-lookup phones.")
    else:
        st.warning(
            "People-Data OFF — no vendor URL/key needed to run. "
            "**Paste phones** on War Room leads, then run the agent "
            "(only leads with a phone get queued). "
            "Optional later: PEOPLE_DATA_API_URL + PEOPLE_DATA_API_KEY in `.env`."
        )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        zip_code = st.text_input("Agent Zip", value="33615", key="ca_zip")
    with c2:
        limit = st.number_input("Max leads", 1, 25, 10, 1, key="ca_limit")
    with c3:
        fee = st.number_input(
            "Wholesale fee $",
            int(MIN_WHOLESALE_FEE),
            50000,
            int(MIN_WHOLESALE_FEE),
            1000,
            key="ca_fee",
        )
    with c4:
        do_hunt = st.checkbox("Hunt RentCast first", value=True, key="ca_hunt")

    if st.button(
        "Run Contract Agent → Queue",
        type="primary",
        use_container_width=True,
        key="ca_run",
    ):
        with st.spinner("Hunting / enriching / generating offers (no SMS)…"):
            result = run_contract_agent(
                zip_code=zip_code,
                limit=int(limit),
                fee=float(fee),
                buyer_name=buyer_name,
                hunt=bool(do_hunt),
            )
        st.session_state["ca_last_result"] = result
        if result.get("ok"):
            st.success(
                f"Queued **{result.get('queued', 0)}** offer(s) · "
                f"enriched {result.get('enriched', 0)} · "
                f"skipped {result.get('skipped', 0)} · "
                f"hunted {result.get('hunted', 0)}"
            )
        else:
            st.warning(
                f"Queued {result.get('queued', 0)} · skipped {result.get('skipped', 0)} · "
                f"hunted {result.get('hunted', 0)}"
            )
        for err in result.get("errors") or []:
            st.error(err)
        st.rerun()

    last = st.session_state.get("ca_last_result")
    if last and last.get("details"):
        with st.expander("Last agent run details", expanded=False):
            for d in last["details"]:
                price = float(d.get("offer_price") or 0)
                extra = d.get("error") or (f"${price:,.0f}" if price else "")
                st.caption(
                    f"#{d.get('lead_id')} · {d.get('status')} · {d.get('address')} · {extra}"
                )


def _render_offer_queue(buyer_name: str) -> None:
    st.subheader("Offer Queue (human send)")
    st.caption(
        "Prepared cash offers with signing links. Tap **Send** to fire Twilio SMS — "
        "nothing sends until you approve."
    )
    queued = list_queued_offers("QUEUED")
    if not queued:
        st.info("Queue empty. Run Contract Agent to prepare offers.")
        return

    confirm_all = st.checkbox(
        "I confirm Send all queued (explicit SMS to every row below)",
        value=False,
        key="ca_confirm_all",
    )
    if st.button("Send all queued", disabled=not confirm_all, key="ca_send_all"):
        ok_n = 0
        fail_n = 0
        for row in queued:
            res = send_queued_offer(int(row["id"]), buyer_name=buyer_name)
            if res.get("ok"):
                ok_n += 1
            else:
                fail_n += 1
                st.error(f"#{row['id']} {row.get('address')}: {res.get('error')}")
        if ok_n:
            st.success(f"Sent {ok_n} offer SMS · failed {fail_n}")
            st.rerun()
        elif fail_n:
            st.error(f"All {fail_n} sends failed.")

    for row in queued:
        qid = int(row["id"])
        address = row.get("address") or ""
        phone = row.get("phone") or ""
        price = float(row.get("offer_price") or 0)
        deal_id = row.get("deal_id") or ""
        pdf_path = row.get("pdf_path") or ""

        st.markdown(
            f"**#{qid}** · lead `{row.get('lead_id')}` · `{address}` · "
            f"**${price:,.0f}** · `{phone}` · deal `{deal_id}`"
        )
        st.text_area(
            "SMS preview",
            value=row.get("sms_preview") or "",
            height=100,
            disabled=True,
            key=f"ca_prev_{qid}",
        )
        b1, b2 = st.columns([1, 3])
        with b1:
            if st.button("Send", type="primary", key=f"ca_send_{qid}", use_container_width=True):
                res = send_queued_offer(qid, buyer_name=buyer_name)
                if res.get("ok"):
                    st.success(f"Sent · SID `{res.get('sid')}`")
                    st.rerun()
                else:
                    st.error(res.get("error") or "Send failed")
        with b2:
            if pdf_path and Path(pdf_path).exists():
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "Download PDF",
                        f,
                        file_name=Path(pdf_path).name,
                        mime="application/pdf",
                        key=f"ca_pdf_{qid}",
                    )
            else:
                st.caption("PDF path missing on disk.")
        st.markdown("---")


def render_war_room(buyer_name: str = "DealShark") -> None:
    st.title("Tampa War Room")
    st.caption(
        "Contract Agent · offer queue · portfolio · flood risk · bulk follow-up."
    )

    selected_id = st.session_state.get("wr_selected_lead_id")
    if selected_id is not None:
        if st.button("← Back", key="wr_detail_back"):
            st.session_state.wr_selected_lead_id = None
            st.rerun()

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
    _render_contract_agent(buyer_name)
    st.markdown("---")
    _render_offer_queue(buyer_name)
    st.markdown("---")
    st.subheader("Bulk Follow-up Hammer")
    st.caption(
        "Texts every non-Closed/Dead lead that has a phone number. "
        "Lis Pendens status uses the stop-auction script. "
        "This is follow-up only — not cash-offer signing links."
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
                "Run Contract Agent (People Data) or paste phones on leads."
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
            "No leads yet. Run **Contract Agent**, Seller Factory hunt, or "
            "Calculator → Save Lead to War Room."
        )
        return

    rows = []
    for r in leads:
        rows.append(
            {
                "ID": r["id"],
                "Address": r.get("address") or "",
                "Zip": r.get("zip_code") or "",
                "Score": int(r.get("motivation_score") or 0),
                "Tier": r.get("motivation_tier") or "",
                "ARV": float(r.get("arv") or 0),
                "MAO": float(r.get("mao") or 0),
                "Fee": float(r.get("wholesale_fee") or 0),
                "Vacant": bool(r.get("vacant")),
                "Absentee": bool(r.get("absentee")),
                "FC Case": r.get("foreclosure_case") or "",
                "Title": r.get("title_status") or "Not Sent",
                "Buyer": r.get("buyer_status") or "None",
                "Risk": r.get("risk_level") or "Standard",
                "Flood": bool(r.get("flood_risk")),
                "Status": r.get("status") or "New Lead",
                "Phone": r.get("seller_phone") or "",
                "Email": r.get("seller_email") or "",
                "Last Contact": r.get("last_contacted") or "—",
                "Date": r.get("date_added") or "",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(_style_war_room(df), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Lead Actions")
    if voice_configured():
        st.caption(f"Click-to-call rings **{agent_phone()}** first, then bridges the lead.")
    else:
        st.caption(
            "Click-to-call needs TWILIO_* keys + a real TWILIO_AGENT_PHONE or NOTIFY_PHONE "
            "(your cell, E.164 — not a +1555 placeholder)."
        )

    selected_id = st.session_state.get("wr_selected_lead_id")
    selected = None
    if selected_id is not None:
        try:
            selected = next((r for r in leads if int(r["id"]) == int(selected_id)), None)
        except (TypeError, ValueError):
            selected = None
        if selected is None:
            st.session_state.wr_selected_lead_id = None
            selected_id = None

    def _render_lead_actions(r: dict) -> None:
        flood_tag = " · FLOOD" if r.get("flood_risk") else ""
        st.markdown(
            f"### #{r['id']} · {r.get('status')} · {r.get('address')} · "
            f"MAO ${float(r.get('mao') or 0):,.0f}{flood_tag} · "
            f"Score {int(r.get('motivation_score') or 0)} ({r.get('motivation_tier') or '—'})"
        )
        tags = (r.get("motive_tags") or "").strip()
        if tags:
            st.caption(tags)
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
            st.write(f"**Seller:** {r.get('seller_name') or '—'}")
            st.write(f"**Mailing:** {r.get('mailing_address') or '—'}")
            st.write(f"**Risk:** {r.get('risk_level')}")
            st.write(
                f"**Title:** {r.get('title_status') or 'Not Sent'} · "
                f"**Buyer:** {r.get('buyer_status') or 'None'}"
            )
            phone_in = st.text_input(
                "Cell (paste from TruePeopleSearch / Lusha)",
                value=r.get("seller_phone") or "",
                key=f"wr_phone_{r['id']}",
                placeholder="+1813...",
            )
            if st.button("Save Phone", key=f"wr_save_phone_{r['id']}"):
                update_lead_phone(int(r["id"]), phone_in)
                st.toast(f"#{r['id']} phone saved")
                st.rerun()
        with c3:
            phone = (phone_in or r.get("seller_phone") or "").strip()
            call_col, sms_col = st.columns(2)
            with call_col:
                if st.button("Click to Call", key=f"wr_call_{r['id']}", use_container_width=True):
                    if not phone:
                        st.error("No phone on this lead.")
                    elif not voice_configured():
                        st.error(
                            "Set TWILIO_AGENT_PHONE or NOTIFY_PHONE to your real cell "
                            "(E.164, e.g. +18135551212) - placeholders like +1555... are blocked."
                        )
                    else:
                        result = click_to_call(
                            phone,
                            label=str(r.get("address") or r["id"]),
                        )
                        if result.get("ok"):
                            mark_contacted(int(r["id"]))
                            st.success(result.get("message") or "Calling...")
                            st.caption(
                                f"Agent SID `{result.get('agent_sid')}` · "
                                f"Lead SID `{result.get('lead_sid') or '—'}` · "
                                f"mode={result.get('mode')}"
                            )
                        else:
                            st.error(result.get("error") or "Call failed")
                            st.caption(
                                "Need a real agent cell + Twilio Voice webhook on your number. "
                                "Trial accounts: verify both phones in Twilio Console."
                            )
            with sms_col:
                if st.button("SMS", key=f"wr_sms_{r['id']}", type="primary", use_container_width=True):
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
                            st.success(f"SMS sent. SID: `{sid}`")
                            st.rerun()
                        else:
                            st.error("SMS failed — check Twilio keys / From number (+1...).")
                            st.caption("Trial Twilio: recipient must be a verified number.")

    if selected is not None:
        _render_lead_actions(selected)
        return

    for r in leads:
        flood_tag = " · FLOOD" if r.get("flood_risk") else ""
        label = (
            f"#{r['id']} · {r.get('status')} · {r.get('address')} · "
            f"MAO ${float(r.get('mao') or 0):,.0f}{flood_tag}"
        )
        list_c1, list_c2 = st.columns([5, 1])
        with list_c1:
            st.write(label)
        with list_c2:
            if st.button("Open", key=f"wr_open_{r['id']}", use_container_width=True):
                st.session_state.wr_selected_lead_id = int(r["id"])
                st.rerun()
