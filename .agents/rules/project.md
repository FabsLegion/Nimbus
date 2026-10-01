# Project rules
- Stack: Python, Streamlit, ChromaDB, PyMuPDF, SQLite, sentence-transformers.
- Code folders: src/rag, src/services, src/database; pages/ for Streamlit pages; app.py is the student UI.
- The LLM is not the source of truth. Facts come from retrieved documents and the SQLite database.
- Version choice and the document checklist are plain Python. The LLM only explains.
- All LLM calls go through src/services/llm.py::ask_llm.
- Actionable answers end with "What to do next:".
- Never invent requirements, dates or policies. If nothing is retrieved, escalate to an office.
- Keep code simple and commented. Do not add libraries without asking.
- Never print or commit the contents of .env.
