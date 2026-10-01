import json
import streamlit as st
from src.database.db import conn
from src.services.assistant import answer, get_student
from src.services.checklist import checklist, guess, REQS

st.set_page_config(page_title="Scholarship Assistant", layout="wide")
T = json.load(open("data/master_timeline.json"))
ss = st.session_state

st.sidebar.header("Mock login")
st.sidebar.button("Login with Google", disabled=True)
st.sidebar.button("Login with Outlook", disabled=True)
sid = st.sidebar.selectbox("Demo Student", ["STU001", "STU002", "STU003", "STU004"])
s = get_student(sid)
key = f"msgs_{sid}"
ss.setdefault(key, []); ss.setdefault("chosen", {}); ss.setdefault("pending", {})

st.title("Scholarship Assistant")
st.caption(f"{s['name']} | {s['branch']} | {s['year']}")
chat, side = st.columns([2, 1])

def ask(q):
    res = answer(sid, q, ss.chosen.get(sid))
    if res["status"] == "clarify":
        ss.pending[sid] = (q, res)
    else:
        ss[key].append(("assistant", res["answer"], res["sources"]))

with chat:
    for role, text, *src in ss[key]:
        with st.chat_message(role):
            st.write(text)
            if src and src[0]:
                st.caption("Sources: " + ", ".join(src[0]))
    if sid in ss.pending:                                   # clarification buttons
        q, res = ss.pending[sid]
        st.info(res["answer"])
        for o in res["options"]:
            if st.button(o):
                ss.chosen[sid] = o
                del ss.pending[sid]
                ask(q)
                st.rerun()
    if q := st.chat_input("Ask about your scholarship"):
        ss[key].append(("user", q, []))
        ask(q)
        st.rerun()

with side:
    t1, t2, t3 = st.tabs(["Checklist", "Timeline", "Alerts"])
    sch = ss.chosen.get(sid) or s["scholarship"]
    with t1:
        if sch:
            icons = {"OK": "✅", "MISSING": "❌", "INVALID": "⚠️", "WRONG_CATEGORY": "🔀"}
            for name, status, why in checklist(sid, sch):
                st.write(f"{icons[status]} **{name}** {status.replace('_', ' ')}")
                if why: st.caption(why)
            up = st.file_uploader("Upload a document")
            cat = st.selectbox("Category", REQS[sch])
            if up and guess(up.name) and guess(up.name) != cat:
                st.warning(f"This looks like **{guess(up.name)}** but you chose **{cat}**.")
            if st.button("Submit application"):
                st.success("Submission received. Next: verification " + T["verification"] + ".")
        else:
            st.write("Pick a scholarship in the chat to see your checklist.")
    with t2:
        for k, v in T.items():
            st.write(f"**{k.replace('_', ' ').title()}**: {v}")
    with t3:
        rows = conn().execute("SELECT priority,message FROM notifications WHERE student_id=? ORDER BY id DESC", (sid,)).fetchall()
        for r in rows: st.error(f"🔴 {r['priority']}: {r['message']}")
        if not rows: st.write("No alerts")
