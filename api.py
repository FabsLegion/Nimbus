"""Nimbus API. Run: uvicorn api:app --reload   then open http://localhost:8000"""
import json
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from src.database.db import conn
from src.services.assistant import answer, get_student, CATALOG
from src.services.checklist import checklist, guess, REQS
from src.services.llm import LOG

app = FastAPI(title="Nimbus")
T = lambda: json.load(open("data/master_timeline.json"))

class Chat(BaseModel):
    student_id: str
    message: str
    chosen: str | None = None
    language: str | None = None

class Upload(BaseModel):
    student_id: str
    doc_type: str
    file_name: str

@app.get("/")
def home():
    return FileResponse("web/index.html")

@app.get("/api/students")
def students():
    return [dict(r) for r in conn().execute("SELECT student_id,name FROM students")]

@app.get("/api/state/{sid}")
def state(sid: str, scholarship: str | None = None):
    s = get_student(sid)
    sch = scholarship or s["scholarship"]
    notes = [dict(r) for r in conn().execute(
        "SELECT priority,message,ts FROM notifications WHERE student_id=? ORDER BY id DESC", (sid,))]
    return {"student": s, "scholarship": sch, "catalog": CATALOG, "timeline": T(), "notifications": notes,
            "required": REQS.get(sch, []), "checklist": checklist(sid, sch) if sch in REQS else []}

@app.post("/api/chat")
def chat(c: Chat):
    return answer(c.student_id, c.message, c.chosen, lang_override=c.language)

@app.post("/api/upload")
def upload(u: Upload):
    db = conn()
    db.execute("DELETE FROM documents WHERE student_id=? AND doc_type=?", (u.student_id, u.doc_type))
    db.execute("INSERT INTO documents(student_id,doc_type,file_name,status,reason) VALUES (?,?,?,?,?)",
               (u.student_id, u.doc_type, u.file_name, "ok", ""))
    db.commit()
    g = guess(u.file_name)
    warn = f"'{u.file_name}' looks like {g}, not {u.doc_type}." if g and g != u.doc_type else ""
    return {"warning": warn}

@app.get("/api/admin")
def admin():
    db = conn()
    q = [dict(r) for r in db.execute("SELECT * FROM queries ORDER BY id DESC")]
    problems = [{"student": s["student_id"], "document": n, "problem": st, "detail": w}
                for s in db.execute("SELECT student_id,scholarship FROM students WHERE scholarship!=''")
                for n, st, w in checklist(s["student_id"], s["scholarship"]) if st != "OK"]
    cats = {}
    for r in q: cats[r["category"]] = cats.get(r["category"], 0) + 1
    return {"total": len(q), "unresolved": [r for r in q if not r["resolved"]], "recent": q[:10],
            "categories": cats, "problems": problems, "llm_log": LOG[-10:]}
