import json
import streamlit as st
from src.database.db import conn, get_timeline
from src.services.assistant import answer, get_student
from src.services.checklist import checklist, guess, REQS

T = get_timeline()

def student_view():
    ss = st.session_state

    # Custom styling for cards, pills, stepper, and banners
    st.markdown("""
    <style>
        /* Card Styling */
        .glass-card {
            background: linear-gradient(135deg, rgba(25, 34, 56, 0.75), rgba(15, 23, 42, 0.85));
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin-bottom: 0.85rem;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        }
        
        /* Status Banners */
        .banner-action {
            background: rgba(239, 68, 68, 0.12);
            border-left: 4px solid #ef4444;
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: #fca5a5;
            font-weight: 600;
            margin-bottom: 0.75rem;
        }
        .banner-clear {
            background: rgba(16, 185, 129, 0.12);
            border-left: 4px solid #10b981;
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: #6ee7b7;
            font-weight: 600;
            margin-bottom: 0.75rem;
        }
        .banner-escalated {
            background: rgba(59, 130, 246, 0.12);
            border-left: 4px solid #3b82f6;
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: #93c5fd;
            font-weight: 600;
            margin-bottom: 0.75rem;
        }
        .banner-scope {
            background: rgba(245, 158, 11, 0.12);
            border-left: 4px solid #f59e0b;
            border-radius: 8px;
            padding: 0.75rem 1rem;
            color: #fcd34d;
            font-weight: 600;
            margin-bottom: 0.75rem;
        }
        
        /* Source Chips */
        .source-chip {
            display: inline-flex;
            align-items: center;
            background: rgba(20, 184, 166, 0.15);
            border: 1px solid rgba(20, 184, 166, 0.35);
            color: #5eead4;
            padding: 0.2rem 0.6rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            margin-right: 0.4rem;
            margin-top: 0.4rem;
            font-family: monospace;
        }
        
        /* Conflict Comparison Box */
        .conflict-box {
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-radius: 10px;
            padding: 0.85rem;
            margin: 0.75rem 0;
        }
        .conflict-col-old {
            background: rgba(239, 68, 68, 0.08);
            border: 1px dashed rgba(239, 68, 68, 0.3);
            border-radius: 8px;
            padding: 0.75rem;
            height: 100%;
        }
        .conflict-col-new {
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 8px;
            padding: 0.75rem;
            height: 100%;
        }

        /* Numbered Step Items */
        .step-item {
            display: flex;
            align-items: flex-start;
            margin-bottom: 0.5rem;
        }
        .step-num {
            background: #14b8a6;
            color: #0b1120;
            font-weight: 700;
            font-size: 0.75rem;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-right: 0.6rem;
            flex-shrink: 0;
            margin-top: 2px;
        }

        /* Status Pills */
        .status-pill {
            display: inline-block;
            padding: 0.2rem 0.55rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        .pill-ok { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
        .pill-missing { background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); }
        .pill-invalid { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
        .pill-wrong { background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.4); }
    </style>
    """, unsafe_allow_html=True)

    # Sidebar controls
    st.sidebar.markdown("### 🔐 Authentication")
    st.sidebar.button("Login with Google", disabled=True, use_container_width=True)
    st.sidebar.button("Login with Outlook", disabled=True, use_container_width=True)
    st.sidebar.divider()

    st.sidebar.markdown("### 👤 Student Profile")
    sid = st.sidebar.selectbox("Active Student ID", ["STU001", "STU002", "STU003", "STU004"])
    s = get_student(sid)

    # Language Selector override
    lang_opts = ["English", "Kannada", "Hindi"]
    default_lang_idx = lang_opts.index(s["language"]) if s["language"] in lang_opts else 0
    selected_lang = st.sidebar.selectbox("Preferred Language", lang_opts, index=default_lang_idx)

    st.sidebar.info(f"**Name:** {s['name']}\n\n**Branch:** {s['branch']}\n\n**Year:** {s['year']}")

    key = f"msgs_{sid}"
    ss.setdefault(key, [])
    ss.setdefault("chosen", {})
    ss.setdefault("pending", {})
    ss.setdefault(f"submitted_{sid}", False)

    sch = ss.chosen.get(sid) or s["scholarship"]

    # Calculate Application Progress
    total_docs = 0
    ok_docs = 0
    if sch and sch in REQS:
        items = checklist(sid, sch)
        total_docs = len(items)
        ok_docs = sum(1 for item in items if item[1] == "OK")
    progress_val = (ok_docs / total_docs) if total_docs > 0 else 0.0

    # Hero Header Section
    h_col1, h_col2 = st.columns([3, 1])
    with h_col1:
        st.title("🎓 Nimbus Scholarship Assistant")
        sub_text = f"Logged in as **{s['name']}** ({s['branch']} · {s['year']})"
        if sch:
            sub_text += f" | Enrolled: **{sch}**"
        st.markdown(sub_text)
    with h_col2:
        st.markdown(f"""
        <div style="text-align: right; background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 8px; padding: 0.6rem 0.85rem; margin-top: 0.5rem;">
            <div style="font-size: 0.75rem; color: #fca5a5; font-weight: 600; text-transform: uppercase;">Deadline</div>
            <div style="font-size: 1.15rem; font-weight: 700; color: #fee2e2;">{T['deadline']}</div>
        </div>
        """, unsafe_allow_html=True)

    # Progress bar banner
    if sch:
        st.write("")
        p_c1, p_c2 = st.columns([4, 1])
        with p_c1:
            st.progress(progress_val)
        with p_c2:
            st.caption(f"**Verification:** {ok_docs}/{total_docs} OK ({int(progress_val*100)}%)")

    st.write("")

    # Submission Received Screen overlay if submitted
    if ss.get(f"submitted_{sid}"):
        st.success("🎉 **Application Submitted Successfully!**")
        st.markdown(f"""
        <div class="glass-card" style="border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.08);">
            <h4 style="color: #34d399; margin-top: 0;">Submission Acknowledgement Received</h4>
            <p>Your documents have been encrypted and submitted to the university scholarship scrutinizing team.</p>
            <ul>
                <li><strong>Verification Window:</strong> {T['verification']}</li>
                <li><strong>Results Announcement:</strong> {T['results']}</li>
                <li><strong>Next Round Allocation:</strong> {T['next_round']}</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("← Return to Assistant"):
            ss[f"submitted_{sid}"] = False
            st.rerun()

    chat_col, side_col = st.columns([1.8, 1.2])

    def ask(q):
        res = answer(sid, q, ss.chosen.get(sid), lang_override=selected_lang)
        if res["status"] == "clarify":
            ss.pending[sid] = (q, res)
        else:
            ss[key].append(("assistant", res))

    with chat_col:
        # Chat message history
        for item in ss[key]:
            role = item[0]
            if role == "user":
                with st.chat_message("user"):
                    st.write(item[1])
            else:
                res = item[1]
                with st.chat_message("assistant"):
                    # 1. Status Banner
                    st_val = res.get("status", "info")
                    if st_val == "action_required":
                        st.markdown('<div class="banner-action">⚠️ Action Required: Document updates needed before deadline</div>', unsafe_allow_html=True)
                    elif st_val == "all_clear":
                        st.markdown('<div class="banner-clear">✅ All Clear: Your documentation meets all current requirements</div>', unsafe_allow_html=True)
                    elif st_val == "escalated":
                        office_name = res.get("office", "Office")
                        st.markdown(f'<div class="banner-escalated">ℹ️ Escalated: Handled directly by {office_name}</div>', unsafe_allow_html=True)
                    elif st_val == "out_of_scope":
                        st.markdown('<div class="banner-scope">⛔ Out of Scope: Outside university scholarship policy</div>', unsafe_allow_html=True)

                    # 2. Conflict Card (if active)
                    conflict = res.get("conflict")
                    if conflict:
                        st.markdown(f"""
                        <div class="conflict-box">
                            <div style="font-size: 0.8rem; font-weight: 700; color: #fbbf24; text-transform: uppercase; margin-bottom: 0.5rem;">
                                ⚠️ Policy Conflict Detected: {conflict['current_year']} Rule Supersedes {conflict['older_year']} Rule
                            </div>
                            <div style="display: flex; gap: 0.75rem;">
                                <div class="conflict-col-old" style="flex: 1;">
                                    <span style="font-size: 0.7rem; color: #f87171; font-weight: 700;">SUPERSEDED ({conflict['older_year']})</span>
                                    <p style="margin: 0.35rem 0 0 0; font-size: 0.85rem; text-decoration: line-through; color: #94a3b8;">
                                        {conflict['older_rule']}
                                    </p>
                                    <div style="font-size: 0.7rem; color: #64748b; margin-top: 0.35rem;">File: {conflict['older_source']}</div>
                                </div>
                                <div class="conflict-col-new" style="flex: 1;">
                                    <span style="font-size: 0.7rem; color: #34d399; font-weight: 700;">CURRENT RULE ({conflict['current_year']})</span>
                                    <p style="margin: 0.35rem 0 0 0; font-size: 0.85rem; font-weight: 600; color: #f8fafc;">
                                        {conflict['current_rule']}
                                    </p>
                                    <div style="font-size: 0.7rem; color: #14b8a6; margin-top: 0.35rem;">File: {conflict['current_source']}</div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    # 3. Concise LLM Explanation (2-3 sentences)
                    st.write(res["answer"])

                    # 4. What to do next Card
                    steps = res.get("steps", [])
                    if steps:
                        st.markdown("""
                        <div class="glass-card" style="border-left: 3px solid #14b8a6; padding: 0.85rem 1.1rem; margin-top: 0.6rem;">
                            <div style="font-weight: 700; font-size: 0.85rem; color: #5eead4; margin-bottom: 0.5rem; text-transform: uppercase; letter-spacing: 0.05em;">
                                What to do next:
                            </div>
                        """, unsafe_allow_html=True)
                        for idx, step in enumerate(steps, start=1):
                            st.markdown(f"""
                            <div class="step-item">
                                <span class="step-num">{idx}</span>
                                <span style="font-size: 0.9rem; color: #f1f5f9;">{step}</span>
                            </div>
                            """, unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)

                    # 5. Escalation Office Card
                    if res.get("office"):
                        st.markdown(f"""
                        <div class="glass-card" style="border-left: 3px solid #3b82f6; background: rgba(59, 130, 246, 0.08); padding: 0.85rem;">
                            <div style="font-weight: 700; color: #93c5fd; font-size: 0.85rem;">🏛️ Relevant Office</div>
                            <div style="font-size: 1rem; font-weight: 600; color: #ffffff; margin-top: 0.2rem;">{res['office']}</div>
                            <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 0.2rem;">Hours: 9:30 AM - 5:00 PM · Admin Block</div>
                        </div>
                        """, unsafe_allow_html=True)

                    # 6. Source Chips
                    sources = res.get("sources", [])
                    if sources:
                        chips_html = "".join([f'<span class="source-chip">📄 {src}</span>' for src in sources])
                        st.markdown(f'<div style="margin-top: 0.4rem;">{chips_html}</div>', unsafe_allow_html=True)

        # Ambiguous scholarship choice buttons
        if sid in ss.pending:
            q, res = ss.pending[sid]
            st.info(res["answer"])
            btn_cols = st.columns(len(res["options"]))
            for idx, opt in enumerate(res["options"]):
                with btn_cols[idx]:
                    if st.button(opt, key=f"opt_{idx}", use_container_width=True):
                        ss.chosen[sid] = opt
                        del ss.pending[sid]
                        ask(q)
                        st.rerun()

        # Suggested Questions
        st.markdown("<div style='font-size: 0.75rem; color: #64748b; margin-top: 0.75rem;'>SUGGESTED QUESTIONS:</div>", unsafe_allow_html=True)
        sq_c1, sq_c2, sq_c3 = st.columns(3)
        with sq_c1:
            if st.button("❓ What's missing?", use_container_width=True):
                q = "What documents are missing or need fixing for my scholarship?"
                ss[key].append(("user", q))
                ask(q)
                st.rerun()
        with sq_c2:
            if st.button("📅 What happens after submit?", use_container_width=True):
                q = "What happens after I submit my application?"
                ss[key].append(("user", q))
                ask(q)
                st.rerun()
        with sq_c3:
            if st.button("📞 Who do I contact?", use_container_width=True):
                q = "Who do I contact about payment and portal support?"
                ss[key].append(("user", q))
                ask(q)
                st.rerun()

        # Chat Input
        if q_input := st.chat_input("Ask about your scholarship or documents..."):
            ss[key].append(("user", q_input))
            ask(q_input)
            st.rerun()

    with side_col:
        tab_check, tab_time, tab_alerts = st.tabs(["Checklist", "Timeline", "Alerts"])

        with tab_check:
            if sch:
                st.markdown(f"#### Requirements: {sch}")
                items = checklist(sid, sch)
                for name, status, why in items:
                    pill_class = {
                        "OK": "pill-ok",
                        "MISSING": "pill-missing",
                        "INVALID": "pill-invalid",
                        "WRONG_CATEGORY": "pill-wrong"
                    }.get(status, "pill-ok")
                    
                    st.markdown(f"""
                    <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 0.6rem 0.85rem; margin-bottom: 0.4rem; display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-weight: 600; color: #f8fafc;">{name}</span>
                        <span class="status-pill {pill_class}">{status.replace('_', ' ')}</span>
                    </div>
                    """, unsafe_allow_html=True)
                    if why:
                        st.caption(f"↳ {why}")

                st.write("")
                st.markdown("##### Upload Document")
                up = st.file_uploader("Select document to upload", key="doc_up")
                cat = st.selectbox("Assign Document Category", REQS.get(sch, []))

                # Wrong category warning detection
                if up and guess(up.name) and guess(up.name) != cat:
                    st.markdown(f"""
                    <div class="glass-card" style="border: 1px solid #f59e0b; background: rgba(245, 158, 11, 0.1);">
                        <strong style="color: #fbbf24;">⚠️ Category Mismatch Warning!</strong><br>
                        File <code>{up.name}</code> looks like a <strong>{guess(up.name)}</strong>, but you selected <strong>{cat}</strong>.
                    </div>
                    """, unsafe_allow_html=True)

                if st.button("🚀 Submit Application", type="primary", use_container_width=True):
                    ss[f"submitted_{sid}"] = True
                    st.balloons()
                    st.rerun()
            else:
                st.info("💡 Pick a scholarship in the chat to see your personalized document checklist.")

        with tab_time:
            st.markdown("#### Application Milestones")
            for k, v in T.items():
                is_deadline = "deadline" in k.lower()
                badge_style = "background: rgba(239, 68, 68, 0.2); color: #fca5a5;" if is_deadline else "background: rgba(20, 184, 166, 0.2); color: #5eead4;"
                st.markdown(f"""
                <div style="border-left: 2px solid #14b8a6; padding-left: 0.85rem; margin-bottom: 0.75rem; position: relative;">
                    <div style="font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">
                        {k.replace('_', ' ')}
                    </div>
                    <div style="font-size: 0.95rem; font-weight: 700; color: #f8fafc; margin-top: 0.15rem;">
                        <span style="display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; {badge_style}">
                            {v}
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with tab_alerts:
            st.markdown("#### System Notifications")
            rows = conn().execute("SELECT priority, message, ts FROM notifications WHERE student_id=? ORDER BY id DESC", (sid,)).fetchall()
            for r in rows:
                p_color = "#ef4444" if r['priority'] == "URGENT" else "#f59e0b"
                st.markdown(f"""
                <div class="glass-card" style="border-left: 3px solid {p_color}; padding: 0.65rem 0.85rem; margin-bottom: 0.5rem;">
                    <span style="font-size: 0.7rem; font-weight: 700; color: {p_color};">🔴 {r['priority']}</span>
                    <div style="font-size: 0.85rem; color: #f1f5f9; margin-top: 0.2rem;">{r['message']}</div>
                    <div style="font-size: 0.7rem; color: #64748b; margin-top: 0.2rem;">{r['ts']}</div>
                </div>
                """, unsafe_allow_html=True)
            if not rows:
                st.caption("No alerts on file. You are in good standing!")

# Configure Streamlit Multi-Page Navigation
pg = st.navigation([
    st.Page(student_view, title="Student Assistant", icon="🎓", default=True),
    st.Page("pages/Admin.py", title="Office Dashboard", icon="📊"),
])
pg.run()
