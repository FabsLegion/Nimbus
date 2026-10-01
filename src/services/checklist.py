from src.database.db import conn

REQS = {
    "Merit Scholarship - Undergraduate": ["Identity Proof", "Income Certificate", "Marksheet", "Bank Document"],
    "Merit Scholarship - Special Category": ["Identity Proof", "Category Certificate", "Marksheet"],
}
KEYWORDS = {"income": "Income Certificate", "caste": "Caste Certificate", "category": "Category Certificate",
            "marksheet": "Marksheet", "aadhaar": "Identity Proof", "bank": "Bank Document"}

def guess(file_name):
    """Guess a document's real type from its file name (simulated document check)."""
    n = file_name.lower()
    return next((t for k, t in KEYWORDS.items() if k in n), None)

def checklist(student_id, scholarship):
    docs = [dict(r) for r in conn().execute("SELECT * FROM documents WHERE student_id=?", (student_id,))]
    by_type = {d["doc_type"]: d for d in docs}
    out = []
    for name in REQS[scholarship]:
        d = by_type.get(name)
        if d is None:
            stray = next((x for x in docs if guess(x["file_name"]) == name), None)
            if stray:
                out.append([name, "WRONG_CATEGORY",
                            f"'{stray['file_name']}' looks like {name} but was uploaded under {stray['doc_type']}"])
            else:
                out.append([name, "MISSING", "Not uploaded"])
        elif d["status"] != "ok":
            out.append([name, "INVALID", d["reason"]])
        else:
            out.append([name, "OK", ""])
    return out
