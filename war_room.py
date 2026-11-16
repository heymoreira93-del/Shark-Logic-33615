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
    CALL_OUTCOMES,
    CRM_STATUSES,
    STATUSES,
    ai_summary_stub,
    append_lead_note,
    daily_call_dashboard,
    get_all_leads,
    get_pending_leads,
    is_do_not_contact,
    list_call_logs,
    list_queued_offers,
    log_call,
    mark_contacted,
    pipeline_stats,
    recent_call_exists,
    set_lead_callback,
    set_lead_dnc,
    update_call_log,
    update_lead_contact,
    update_lead_phone,
    update_lead_status,
)
from hunter import skip_trace
from investor_report import generate_investor_report, generate_investor_reports_batch
from phone_enrich import people_data_configured
from tampa_config import MIN_WHOLESALE_FEE
from voice import agent_phone, click_to_call, voice_configured


def _style_war_room(df: pd.DataFrame):
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

    return df.style.apply(row_style, axis=1)


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


def _render_daily_crm_dashboard() -> None:
    dash = daily_call_dashboard()
    st.subheader("Daily Call Dashboard")
    st.caption(f"Acquisition CRM · {dash['day']} · no auto-dial / auto-SMS")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Calls today", dash["calls_made"])
    m2.metric("Answered", dash["answered"])
    m3.metric("Failed/missed", dash["failed"])
    m4.metric("Callbacks overdue", len(dash["callbacks_due"]))
    m5.metric("Interested sellers", len(dash["interested"]))

    overdue = dash["callbacks_due"]
    upcoming = dash["callbacks_upcoming"]
    if overdue:
        st.error(
            "Overdue callbacks: "
            + "; ".join(
                f"#{c['id']} {c.get('address') or ''} @ {c.get('callback_at')}"
                for c in overdue[:8]
            )
        )
    if upcoming:
        st.warning(
            "Upcoming (48h): "
            + "; ".join(
                f"#{c['id']} {c.get('address') or ''} @ {c.get('callback_at')}"
                for c in upcoming[:8]
            )
        )
    if dash["interested"]:
        st.info(
            "Interested / negotiating: "
            + "; ".join(
                f"#{c['id']} {c.get('status')} · {c.get('address') or ''}"
                for c in dash["interested"][:8]
            )
        )

    recent = list_call_logs(limit=8)
    if recent:
        st.caption("Recent call history")
        st.dataframe(
            [
                {
                    "When": c.get("created_at"),
                    "Lead": c.get("lead_id"),
                    "Address": c.get("address"),
                    "Status": c.get("status"),
                    "Dur(s)": c.get("duration_sec"),
                    "Test": bool(c.get("is_test")),
                    "Error": (c.get("error") or "")[:60],
                }
                for c in recent
            ],
            use_container_width=True,
            hide_index=True,
        )


def render_war_room(buyer_name: str = "DealShark") -> None:
    st.title("Tampa War Room")
    st.caption(
        "Acquisition CRM · call history · follow-ups · Contract Agent · bulk follow-up."
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
    _render_daily_crm_dashboard()
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
        cb = (r.get("callback_at") or "").strip()
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
                "Status": r.get("status") or "Not Contacted",
                "Phone": r.get("seller_phone") or "",
                "Email": r.get("seller_email") or "",
                "Callback": cb or "—",
                "Last Contact": r.get("last_contacted") or "—",
                "Date": r.get("date_added") or "",
            }
        )
    df = pd.DataFrame(rows)
    st.dataframe(_style_war_room(df), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Investor Research Package ($250)")
    st.caption(
        "Downloadable PDF from stored War Room data + optional live comps. "
        "No BatchData/Twilio required. Does not contact sellers or investors."
    )
    include_comps = st.checkbox(
        "Include live RentCast comps when available",
        value=True,
        key="wr_inv_comps",
    )
    exclude_weak = st.checkbox(
        "Exclude weak leads #6 and #120 from sales pack (recommended)",
        value=True,
        key="wr_inv_exclude_weak",
        help="ARV missing/suspicious — do not sell until corrected.",
    )
    if st.button(
        "Batch export investor reports (sales-ready leads)",
        type="primary",
        key="wr_inv_batch",
        use_container_width=True,
    ):
        weak_ids = {6, 120} if exclude_weak else set()
        active = [
            r
            for r in leads
            if (r.get("status") or "")
            not in {"Dead", "Closed", "SIGNED", "Do Not Contact"}
            and int(r.get("id") or 0) not in weak_ids
        ]
        with st.spinner(f"Building {len(active)} investor PDF(s)..."):
            batch = generate_investor_reports_batch(
                active,
                include_live_comps=bool(include_comps),
                make_zip=True,
            )
        if batch.get("ok"):
            st.success(f"Generated {batch['count']} report(s).")
            zpath = batch.get("zip_path")
            if zpath and Path(zpath).exists():
                with open(zpath, "rb") as f:
                    st.download_button(
                        "Download ZIP pack",
                        f,
                        file_name=Path(zpath).name,
                        mime="application/zip",
                        key="wr_inv_zip_dl",
                    )
            for p in batch.get("paths") or []:
                st.caption(str(p))
        else:
            st.error("Batch failed.")
        for err in batch.get("errors") or []:
            st.warning(err)

    st.markdown("---")
    st.subheader("Lead Actions")
    if voice_configured():
        st.caption(
            f"Click-to-call rings **{agent_phone()}** first, then bridges the lead. "
            "Requires your explicit confirm — never auto-dials."
        )
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
        lid = int(r["id"])
        flood_tag = " · FLOOD" if r.get("flood_risk") else ""
        dnc = is_do_not_contact(r)
        st.markdown(
            f"### #{lid} · {r.get('status')} · {r.get('address')} · "
            f"MAO ${float(r.get('mao') or 0):,.0f}{flood_tag} · "
            f"Score {int(r.get('motivation_score') or 0)} ({r.get('motivation_tier') or '—'})"
        )
        if dnc:
            st.error("Do Not Contact — dial/SMS blocked until you clear DNC.")
        tags = (r.get("motive_tags") or "").strip()
        if tags:
            st.caption(tags)

        status_choices = list(CRM_STATUSES) + [
            s for s in STATUSES if s not in CRM_STATUSES
        ]
        cur_status = r.get("status") or "Not Contacted"
        if cur_status not in status_choices:
            status_choices = [cur_status] + status_choices

        c1, c2, c3 = st.columns(3)
        with c1:
            new_status = st.selectbox(
                "Lead Status",
                status_choices,
                index=status_choices.index(cur_status)
                if cur_status in status_choices
                else 0,
                key=f"wr_status_{lid}",
            )
            if st.button("Update Status", key=f"wr_upd_{lid}"):
                update_lead_status(lid, new_status)
                if new_status == "Do Not Contact":
                    set_lead_dnc(lid, True)
                st.toast(f"#{lid} → {new_status}")
                st.rerun()
            if st.button("Mark DNC", key=f"wr_dnc_{lid}"):
                set_lead_dnc(lid, True)
                update_lead_status(lid, "Do Not Contact")
                st.rerun()

        with c2:
            st.write(f"**Seller:** {r.get('seller_name') or '—'}")
            st.write(f"**Mailing:** {r.get('mailing_address') or '—'}")
            st.write(f"**Risk:** {r.get('risk_level')}")
            st.write(
                f"**Title:** {r.get('title_status') or 'Not Sent'} · "
                f"**Buyer:** {r.get('buyer_status') or 'None'}"
            )
            st.write(
                f"**Phone source:** {r.get('phone_source') or '—'} · "
                f"**Confidence:** {r.get('phone_confidence') or '—'}"
            )
            phone_in = st.text_input(
                "Cell (E.164)",
                value=r.get("seller_phone") or "",
                key=f"wr_phone_{lid}",
                placeholder="+1813...",
            )
            ph_col, look_col = st.columns(2)
            with ph_col:
                if st.button("Save Phone", key=f"wr_save_phone_{lid}", use_container_width=True):
                    update_lead_phone(lid, phone_in)
                    update_lead_contact(
                        lid,
                        phone=phone_in,
                        phone_source="manual",
                        phone_confidence="user",
                    )
                    st.toast(f"#{lid} phone saved")
                    st.rerun()
            with look_col:
                if st.button(
                    "Find Seller Phone",
                    key=f"wr_find_phone_{lid}",
                    use_container_width=True,
                ):
                    addr = (r.get("address") or "").strip()
                    hit = skip_trace(addr) if addr else None
                    if not hit:
                        st.error("Lookup failed — no address.")
                    else:
                        phone_hit = (hit.get("phone") or "").strip()
                        email_hit = (hit.get("email") or "").strip()
                        name_hit = (hit.get("owner_name") or "").strip()
                        err = (hit.get("phone_error") or hit.get("error") or "").strip()
                        if phone_hit or email_hit or name_hit:
                            conf = "high" if phone_hit else ("medium" if email_hit else "low")
                            update_lead_contact(
                                lid,
                                phone=phone_hit,
                                email=email_hit,
                                seller_name=name_hit,
                                mailing_address=str(hit.get("mailing_address") or ""),
                                phone_source=str(
                                    hit.get("phone_source") or hit.get("source") or ""
                                ),
                                phone_confidence=conf if phone_hit else "",
                            )
                            st.success(
                                f"Saved: phone={'yes' if phone_hit else 'no'} · "
                                f"email={'yes' if email_hit else 'no'} · "
                                f"source={hit.get('phone_source') or hit.get('source')}"
                            )
                            st.rerun()
                        else:
                            st.warning(
                                err
                                or "No phone/email returned. BatchData may need credits; paste manually."
                            )
                            if not people_data_configured():
                                st.caption("BatchData / people-data key missing.")

        with c3:
            phone = (phone_in or r.get("seller_phone") or "").strip()
            confirm_call = st.checkbox(
                "I confirm this call is lawful (TCPA/DNC) and I want to dial now",
                value=False,
                key=f"wr_confirm_call_{lid}",
            )
            call_col, sms_col = st.columns(2)
            with call_col:
                if st.button("Click to Call", key=f"wr_call_{lid}", use_container_width=True):
                    if dnc or (r.get("status") == "Do Not Contact"):
                        st.error("Lead is Do Not Contact.")
                    elif not confirm_call:
                        st.error("Check the confirm box before dialing.")
                    elif not phone:
                        st.error("No phone on this lead.")
                    elif not voice_configured():
                        st.error(
                            "Set TWILIO_AGENT_PHONE or NOTIFY_PHONE to your real cell "
                            "(E.164)."
                        )
                    elif recent_call_exists(phone):
                        st.warning("Duplicate blocked — same number dialed in the last 2 minutes.")
                    else:
                        result = click_to_call(
                            phone,
                            label=str(r.get("address") or lid),
                        )
                        log_id = log_call(
                            lead_id=lid,
                            address=str(r.get("address") or ""),
                            agent_phone=agent_phone(),
                            lead_phone=phone,
                            mode=str(result.get("mode") or ""),
                            status="initiated" if result.get("ok") else "failed",
                            agent_sid=str(result.get("agent_sid") or ""),
                            lead_sid=str(result.get("lead_sid") or ""),
                            error=str(result.get("error") or ""),
                            notes="",
                            is_test=False,
                        )
                        if result.get("ok"):
                            mark_contacted(lid, status="Attempted")
                            st.success(result.get("message") or "Calling...")
                            st.caption(
                                f"Logged call #{log_id} · Agent `{result.get('agent_sid')}` · "
                                f"Lead `{result.get('lead_sid') or '—'}`"
                            )
                        else:
                            st.error(result.get("error") or "Call failed")
            with sms_col:
                confirm_sms = st.checkbox(
                    "Confirm SMS send",
                    value=False,
                    key=f"wr_confirm_sms_{lid}",
                )
                if st.button("SMS", key=f"wr_sms_{lid}", use_container_width=True):
                    if dnc:
                        st.error("Lead is Do Not Contact.")
                    elif not confirm_sms:
                        st.error("Check Confirm SMS before sending.")
                    elif not phone:
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
                                lid,
                                status="Follow Up"
                                if new_status not in {"Lis Pendens"}
                                else "Lis Pendens",
                            )
                            st.success(f"SMS sent. SID: `{sid}`")
                            st.rerun()
                        else:
                            st.error("SMS failed — check Twilio / Trial verified numbers.")

        st.markdown("#### Investor report")
        if st.button(
            "Generate Investor Report PDF",
            key=f"wr_inv_one_{lid}",
            use_container_width=True,
        ):
            with st.spinner("Building investor PDF..."):
                path = generate_investor_report(
                    r,
                    include_live_comps=bool(
                        st.session_state.get("wr_inv_comps", True)
                    ),
                )
            st.success(f"Report ready: {path}")
            if path.exists():
                with open(path, "rb") as f:
                    st.download_button(
                        "Download this report",
                        f,
                        file_name=path.name,
                        mime="application/pdf",
                        key=f"wr_inv_dl_{lid}",
                    )

        st.markdown("#### Seller notes & follow-up")
        note_in = st.text_area(
            "Add note after conversation",
            key=f"wr_note_{lid}",
            placeholder="Seller wants cash close in 14 days...",
            height=80,
        )
        n1, n2 = st.columns(2)
        with n1:
            if st.button("Save Note", key=f"wr_save_note_{lid}", use_container_width=True):
                if append_lead_note(lid, note_in):
                    st.toast("Note saved")
                    st.rerun()
                else:
                    st.warning("Enter a note first.")
        with n2:
            cb_date = st.date_input("Callback date", key=f"wr_cb_date_{lid}")
            cb_time = st.time_input("Callback time", key=f"wr_cb_time_{lid}")
            if st.button("Schedule Callback", key=f"wr_cb_save_{lid}", use_container_width=True):
                when = f"{cb_date.isoformat()} {cb_time.strftime('%H:%M')}"
                set_lead_callback(lid, when)
                if new_status in {"Not Contacted", "New Lead", "Attempted"}:
                    update_lead_status(lid, "Follow Up")
                st.success(f"Callback set for {when}")
                st.rerun()

        existing_notes = (r.get("notes") or "").strip()
        if existing_notes:
            st.text_area(
                "Notes history",
                value=existing_notes,
                height=120,
                disabled=True,
                key=f"wr_notes_hist_{lid}",
            )
        if (r.get("callback_at") or "").strip():
            st.caption(f"Scheduled callback: **{r.get('callback_at')}**")

        st.markdown("#### Call history")
        logs = list_call_logs(lid, limit=15)
        if not logs:
            st.caption("No calls logged for this lead yet.")
        else:
            for c in logs:
                with st.expander(
                    f"#{c['id']} · {c.get('created_at')} · {c.get('status')} · "
                    f"{c.get('duration_sec') or 0}s",
                    expanded=False,
                ):
                    st.write(
                        f"Phone `{c.get('lead_phone')}` · mode={c.get('mode')} · "
                        f"SIDs agent=`{c.get('agent_sid') or '—'}` lead=`{c.get('lead_sid') or '—'}`"
                    )
                    if c.get("error"):
                        st.error(c.get("error"))
                    outcome = st.selectbox(
                        "Update outcome",
                        list(CALL_OUTCOMES),
                        index=list(CALL_OUTCOMES).index(c["status"])
                        if c.get("status") in CALL_OUTCOMES
                        else 0,
                        key=f"wr_out_{lid}_{c['id']}",
                    )
                    dur = st.number_input(
                        "Duration (sec)",
                        min_value=0,
                        value=int(c.get("duration_sec") or 0),
                        key=f"wr_dur_{lid}_{c['id']}",
                    )
                    call_note = st.text_input(
                        "Call note",
                        value=c.get("notes") or "",
                        key=f"wr_cn_{lid}_{c['id']}",
                    )
                    if st.button("Save call log", key=f"wr_clog_{lid}_{c['id']}"):
                        update_call_log(
                            int(c["id"]),
                            status=outcome,
                            duration_sec=int(dur),
                            notes=call_note,
                        )
                        st.toast("Call log updated")
                        st.rerun()
                    st.caption(ai_summary_stub(call_id=int(c["id"])))
                    if c.get("ai_summary"):
                        st.info(c.get("ai_summary"))

    if selected is not None:
        _render_lead_actions(selected)
        return

    for r in leads:
        flood_tag = " · FLOOD" if r.get("flood_risk") else ""
        cb = (r.get("callback_at") or "").strip()
        cb_tag = f" · CB {cb}" if cb else ""
        phone_tag = " · 📞" if (r.get("seller_phone") or "").strip() else " · NO_PHONE"
        label = (
            f"#{r['id']} · {r.get('status')} · {r.get('address')} · "
            f"MAO ${float(r.get('mao') or 0):,.0f}{flood_tag}{cb_tag}{phone_tag}"
        )
        list_c1, list_c2 = st.columns([5, 1])
        with list_c1:
            st.write(label)
        with list_c2:
            if st.button("Open", key=f"wr_open_{r['id']}", use_container_width=True):
                st.session_state.wr_selected_lead_id = int(r["id"])
                st.rerun()
