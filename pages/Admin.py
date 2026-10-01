import pandas as pd
import streamlit as st
from src.database.db import conn
from src.services.checklist import checklist

st.title("Scholarship Office Dashboard")
q = pd.read_sql("SELECT * FROM queries", conn())
c1, c2 = st.columns(2)
c1.metric("Queries", len(q))
c2.metric("Unresolved", int((q.resolved == 0).sum()))

st.subheader("Most common queries")
st.bar_chart(q.category.value_counts())

rows = []
for s in conn().execute("SELECT student_id, scholarship FROM students WHERE scholarship != ''"):
    for name, status, why in checklist(s["student_id"], s["scholarship"]):
        if status != "OK":
            rows.append({"document": name, "problem": status})

st.subheader("Documents with problems")
d = pd.DataFrame(rows)
if not d.empty:
    st.bar_chart(d["document"].value_counts())
else:
    st.write("None")

st.subheader("Unresolved cases")
st.dataframe(q[q.resolved == 0])
