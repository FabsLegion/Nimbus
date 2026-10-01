import pandas as pd
import streamlit as st
from src.database.db import conn
from src.services.checklist import checklist

# Inject sleek glassmorphism dashboard CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7), rgba(15, 23, 42, 0.8));
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 1.2rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }
    .metric-label {
        font-size: 0.85rem;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
        margin-bottom: 0.25rem;
    }
    .metric-val {
        font-size: 2.2rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #14b8a6;
        margin-top: 0.35rem;
    }
    .section-card {
        background: rgba(19, 28, 49, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 14px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.65rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .badge-resolved {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-escalated {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
</style>
""", unsafe_allow_html=True)

# Dashboard Header
st.title("📊 Scholarship Office Dashboard")
st.caption("Live operational intelligence, document anomalies, and human escalation triage")

# Load Queries Data
q = pd.read_sql("SELECT * FROM queries ORDER BY id DESC", conn())
total_q = len(q)
unresolved_q = int((q.resolved == 0).sum()) if total_q > 0 else 0
resolved_rate = int(((total_q - unresolved_q) / total_q) * 100) if total_q > 0 else 100

# Checklist Problems Across Students
rows = []
for s in conn().execute("SELECT student_id, scholarship FROM students WHERE scholarship != ''"):
    for name, status, why in checklist(s["student_id"], s["scholarship"]):
        if status != "OK":
            rows.append({"student_id": s["student_id"], "document": name, "problem": status, "detail": why})
d_prob = pd.DataFrame(rows)
total_doc_problems = len(d_prob)

# 4 Key Metrics Bar
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Total Inquiries</div>
        <div class="metric-val">{total_q}</div>
        <div class="metric-sub">Logged via Assistant</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="metric-card" style="border-color: rgba(239, 68, 68, 0.3);">
        <div class="metric-label">Unresolved Cases</div>
        <div class="metric-val" style="color: #f87171;">{unresolved_q}</div>
        <div class="metric-sub" style="color: #fca5a5;">Requires Office Action</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-label">Resolution Rate</div>
        <div class="metric-val" style="color: #34d399;">{resolved_rate}%</div>
        <div class="metric-sub">Handled by AI Agent</div>
    </div>
    """, unsafe_allow_html=True)

with m4:
    st.markdown(f"""
    <div class="metric-card" style="border-color: rgba(245, 158, 11, 0.3);">
        <div class="metric-label">Document Issues</div>
        <div class="metric-val" style="color: #fbbf24;">{total_doc_problems}</div>
        <div class="metric-sub" style="color: #fde68a;">Flagged by Checklist</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# Visual Charts
c_left, c_right = st.columns(2)

with c_left:
    st.subheader("Query Categories")
    if not q.empty:
        cat_counts = q["category"].value_counts().reset_index()
        cat_counts.columns = ["Category", "Count"]
        st.bar_chart(cat_counts.set_index("Category"), color="#14b8a6")
    else:
        st.info("No queries recorded yet.")

with c_right:
    st.subheader("Documents Requiring Attention")
    if not d_prob.empty:
        doc_counts = d_prob["document"].value_counts().reset_index()
        doc_counts.columns = ["Document Type", "Issues"]
        st.bar_chart(doc_counts.set_index("Document Type"), color="#f59e0b")
    else:
        st.success("All enrolled student documents are verified!")

st.write("")

# Unresolved Escalations Section
st.subheader("🚨 Unresolved Cases (Escalation Triage)")
unresolved_df = q[q.resolved == 0]
if not unresolved_df.empty:
    st.dataframe(
        unresolved_df[["id", "student_id", "category", "text", "office", "ts"]].rename(
            columns={
                "id": "ID",
                "student_id": "Student",
                "category": "Category",
                "text": "Inquiry",
                "office": "Routed Office",
                "ts": "Timestamp"
            }
        ),
        use_container_width=True,
        hide_index=True
    )
else:
    st.success("All cases are resolved! No pending office escalations.")

st.write("")

# Live Activity Feed
st.subheader("⏱️ Recent Inquiries Stream")
recent_q = q.head(10)
if not recent_q.empty:
    for _, row in recent_q.iterrows():
        is_res = row["resolved"] == 1
        badge_html = '<span class="status-badge badge-resolved">✓ Resolved</span>' if is_res else f'<span class="status-badge badge-escalated">⚠ Escalated: {row["office"]}</span>'
        with st.container():
            st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="font-weight: 700; color: #14b8a6; margin-right: 0.75rem;">{row['student_id']}</span>
                    <span style="color: #94a3b8; font-size: 0.85rem; margin-right: 0.75rem;">[{row['category']}]</span>
                    <span style="color: #f1f5f9;">{row['text']}</span>
                </div>
                <div>
                    {badge_html}
                    <span style="color: #64748b; font-size: 0.75rem; margin-left: 0.75rem;">{row['ts']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
