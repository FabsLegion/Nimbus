import pandas as pd
import streamlit as st
from src.database.db import conn

st.title("Scholarship Office Dashboard")
q = pd.read_sql("SELECT * FROM queries", conn())
c1, c2 = st.columns(2)
c1.metric("Queries", len(q))
c2.metric("Unresolved", int((q.resolved == 0).sum()))
st.subheader("Most common queries")
st.bar_chart(q.category.value_counts())
st.subheader("Documents with problems")
d = pd.read_sql("SELECT doc_type, status FROM documents WHERE status != 'ok'", conn())
st.bar_chart(d.doc_type.value_counts()) if len(d) else st.write("None")
st.subheader("Unresolved cases")
st.dataframe(q[q.resolved == 0])
