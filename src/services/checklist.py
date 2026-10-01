from src.database.db import conn, get_required_documents, get_doc_keywords, get_all_required_documents

class _ReqsProxy(dict):
    """Dynamic proxy for required documents queried from the database."""
    def get(self, key, default=None):
        reqs = get_required_documents(key)
        return reqs if reqs else (default if default is not None else [])
    def __getitem__(self, key):
        reqs = get_required_documents(key)
        if not reqs:
            raise KeyError(key)
        return reqs
    def __contains__(self, key):
        return len(get_required_documents(key)) > 0
    def items(self):
        return get_all_required_documents().items()

REQS = _ReqsProxy()

def guess(file_name):
    """Guess a document's real type from its file name using database-configured keywords."""
    n = file_name.lower()
    doc_keywords = get_doc_keywords()
    return next((t for k, t in doc_keywords.items() if k in n), None)

def checklist(student_id, scholarship):
    docs = [dict(r) for r in conn().execute("SELECT * FROM documents WHERE student_id=?", (student_id,))]
    by_type = {d["doc_type"]: d for d in docs}
    out = []
    required = get_required_documents(scholarship)
    for name in required:
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
