import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Header
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from src.database.db import (
    conn,
    get_catalog,
    get_timeline,
    get_timeline_list,
    get_offices_list,
    get_scholarship_facts,
    get_announcements,
    get_setting,
    set_setting,
    add_audit_log,
    get_audit_logs,
    get_all_required_documents,
)
from src.database.models import Application
from src.services.assistant import answer, get_student, CATALOG
from src.services.checklist import checklist, guess, REQS
from src.services.notifications import sync_student_notifications
from src.services.data_admin import (
    parse_import_file,
    validate_and_preview,
    commit_import_rows,
    list_table_rows,
    create_table_row,
    update_table_row,
    delete_table_row,
)
from src.services.llm import LOG
from src.services.auth import (
    register_student,
    authenticate_student,
    verify_admin_passcode,
    create_admin_session,
    verify_admin_token,
    get_student_id_from_token,
    get_session_info,
)
from src.services.kb import (
    extract_document_text_and_chunks,
    extract_draft_metadata,
    create_draft,
    get_draft,
    list_drafts,
    publish_draft,
    delete_draft,
)

app = FastAPI(title="Nimbus")
app.mount("/assets", StaticFiles(directory="web"), name="assets")
T = get_timeline

# --- Pydantic Schemas ---

class StudentRegister(BaseModel):
    student_id: str
    name: str
    branch: str
    year: str
    category: Optional[str] = "General"
    language: Optional[str] = "English"
    pin: str

class StudentLogin(BaseModel):
    student_id: str
    pin: str

class AdminLogin(BaseModel):
    passcode: str

class ChooseScholarship(BaseModel):
    scholarship: str

class Chat(BaseModel):
    student_id: Optional[str] = None
    message: str
    chosen: Optional[str] = None
    language: Optional[str] = None

class Upload(BaseModel):
    student_id: Optional[str] = None
    doc_type: str
    file_name: str

class PublishPayload(BaseModel):
    scholarship_name: Optional[str] = None
    kind: Optional[str] = None
    year: Optional[int] = None
    version: Optional[int] = None
    required_documents: Optional[list[str]] = None
    dates: Optional[dict[str, str]] = None
    offices: Optional[list[dict[str, str]]] = None

# --- Auth Helpers ---

def extract_token(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth[7:].strip()
    if request.headers.get("X-Session-Token"):
        return request.headers.get("X-Session-Token").strip()
    if request.cookies.get("session_token"):
        return request.cookies.get("session_token").strip()
    return None

def require_admin(request: Request):
    token = extract_token(request)
    if not token or not verify_admin_token(token):
        raise HTTPException(status_code=401, detail="Admin authorization required")
    return token

def resolve_student_id(request: Request, fallback_id: Optional[str] = None) -> str:
    token = extract_token(request)
    if token:
        sid = get_student_id_from_token(token)
        if sid:
            return sid
    if fallback_id:
        return fallback_id
    raise HTTPException(status_code=401, detail="Student authentication required")

# --- HTML Portal Routes ---

@app.get("/")
@app.get("/intro")
@app.get("/intro.html")
def landing_page():
    return FileResponse("web/intro.html")

@app.get("/student")
@app.get("/student.html")
def student_portal_page():
    return FileResponse("web/student.html")

@app.get("/admin")
@app.get("/admin.html")
@app.get("/office")
@app.get("/office.html")
def admin_portal_page():
    return FileResponse("web/office.html")

# --- Authentication Endpoints ---

@app.post("/api/auth/register")
def auth_register(payload: StudentRegister):
    success, msg, token = register_student(
        student_id=payload.student_id,
        name=payload.name,
        branch=payload.branch,
        year=payload.year,
        category=payload.category or "General",
        language=payload.language or "English",
        pin=payload.pin,
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    student = get_student(payload.student_id)
    return {"token": token, "student": student, "message": msg}

@app.post("/api/auth/login")
def auth_login(payload: StudentLogin):
    success, msg, token = authenticate_student(payload.student_id, payload.pin)
    if not success:
        raise HTTPException(status_code=401, detail=msg)
    student = get_student(payload.student_id)
    return {"token": token, "student": student, "message": msg}

@app.post("/api/auth/admin-login")
def auth_admin_login(payload: AdminLogin):
    if not verify_admin_passcode(payload.passcode):
        raise HTTPException(status_code=401, detail="Invalid admin passcode")
    token = create_admin_session()
    return {"token": token, "message": "Admin authorization successful"}

@app.get("/api/auth/me")
def auth_me(request: Request):
    token = extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    info = get_session_info(token)
    if not info:
        raise HTTPException(status_code=401, detail="Invalid session")
    if info["role"] == "student":
        student = get_student(info["user_id"])
        return {"role": "student", "user_id": info["user_id"], "student": student}
    return {"role": "admin", "user_id": "admin"}

# --- Student Portal Endpoints ---

@app.get("/api/students")
def students():
    return [dict(r) for r in conn().execute("SELECT student_id,name FROM students")]

@app.get("/api/state")
def student_state_authenticated(request: Request, scholarship: Optional[str] = None):
    sid = resolve_student_id(request)
    return state(sid, scholarship)

@app.get("/api/state/{sid}")
def state(sid: str, scholarship: Optional[str] = None):
    s = get_student(sid)
    sch = scholarship or s.get("scholarship", "")
    
    # Sync 4-priority notifications from checklist and timeline
    try:
        sync_student_notifications(sid)
    except Exception:
        pass

    notes = [dict(r) for r in conn().execute(
        "SELECT priority,message,ts FROM notifications WHERE student_id=? ORDER BY id DESC", (sid,))]
    
    # Check if application has already been submitted
    app_row = conn().execute("SELECT * FROM applications WHERE student_id=? ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
    submitted_app = dict(app_row) if app_row else None

    reqs_map = get_all_required_documents()
    facts = get_scholarship_facts(sch) if sch else []
    announcements = get_announcements(active_only=True)
    deadline_banner = get_setting("deadline_banner", default="Applications close Tonight, 11:59 PM. Verify all required documents!")
    offices = get_offices_list()
    timeline_list = get_timeline_list()

    return {
        "student": s,
        "scholarship": sch,
        "catalog": list(CATALOG),
        "timeline": T(),
        "timeline_list": timeline_list,
        "notifications": notes,
        "required": reqs_map.get(sch, []),
        "checklist": checklist(sid, sch) if sch in reqs_map else [],
        "application": submitted_app,
        "facts": facts,
        "announcements": announcements,
        "deadline_banner": deadline_banner,
        "offices": offices,
    }

@app.post("/api/scholarship/choose")
def choose_scholarship(payload: ChooseScholarship, request: Request):
    sid = resolve_student_id(request)
    db = conn()
    db.execute("UPDATE students SET scholarship=? WHERE student_id=?", (payload.scholarship, sid))
    db.commit()
    return {"status": "ok", "scholarship": payload.scholarship}

@app.post("/api/chat")
def chat(c: Chat, request: Request):
    sid = resolve_student_id(request, fallback_id=c.student_id)
    return answer(sid, c.message, c.chosen, lang_override=c.language)

@app.post("/api/upload")
def upload(u: Upload, request: Request):
    sid = resolve_student_id(request, fallback_id=u.student_id)
    db = conn()
    db.execute("DELETE FROM documents WHERE student_id=? AND doc_type=?", (sid, u.doc_type))
    db.execute("INSERT INTO documents(student_id,doc_type,file_name,status,reason) VALUES (?,?,?,?,?)",
               (sid, u.doc_type, u.file_name, "ok", ""))
    db.commit()
    g = guess(u.file_name)
    warn = f"'{u.file_name}' looks like {g}, not {u.doc_type}." if g and g != u.doc_type else ""
    return {"warning": warn}

@app.post("/api/application/submit")
def submit_application(request: Request):
    sid = resolve_student_id(request)
    s = get_student(sid)
    sch = s.get("scholarship", "")
    if not sch:
        raise HTTPException(status_code=400, detail="Please choose a scholarship before submitting.")
    
    items = checklist(sid, sch)
    unresolved = [i for i in items if i[1] != "OK"]
    if unresolved:
        raise HTTPException(status_code=400, detail=f"Cannot submit application: {len(unresolved)} required document(s) missing or need attention.")

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    db = conn()
    db.execute("INSERT INTO applications(student_id, scholarship_name, status, submitted_at) VALUES (?, ?, 'submitted', ?)",
               (sid, sch, now_str))
    db.commit()
    t = get_timeline()
    return {
        "status": "submitted",
        "scholarship": sch,
        "verification_dates": t.get("verification", "03 Oct to 07 Oct"),
        "results_date": t.get("results", "10 Oct"),
        "allotment_date": t.get("allotment", "15 Oct"),
    }

# --- Admin Portal Endpoints (Token Protected) ---

@app.get("/api/admin")
def admin(request: Request):
    require_admin(request)
    db = conn()
    q = [dict(r) for r in db.execute("SELECT * FROM queries ORDER BY id DESC")]
    problems = [{"student": s["student_id"], "document": n, "problem": st, "detail": w}
                for s in db.execute("SELECT student_id,scholarship FROM students WHERE scholarship!=''")
                for n, st, w in checklist(s["student_id"], s["scholarship"]) if st != "OK"]
    cats = {}
    for r in q:
        cats[r["category"]] = cats.get(r["category"], 0) + 1
    return {
        "total": len(q),
        "unresolved": [r for r in q if not r["resolved"]],
        "recent": q[:10],
        "categories": cats,
        "problems": problems,
        "llm_log": LOG[-10:]
    }

# --- Knowledge Base Admin Endpoints (Token Protected) ---

@app.post("/admin/kb/upload")
async def kb_upload(request: Request, file: UploadFile = File(...)):
    require_admin(request)
    content = await file.read()
    filename = file.filename or "uploaded_document.pdf"
    full_text, chunks = extract_document_text_and_chunks(content, filename)
    extracted = extract_draft_metadata(full_text)
    draft = create_draft(filename, extracted, chunks)
    return {
        "id": draft.id,
        "file_name": draft.file_name,
        "scholarship_name": draft.scholarship_name,
        "kind": getattr(draft, "kind", "scholarship"),
        "year": draft.year,
        "version": draft.version,
        "required_documents": json.loads(draft.required_documents_json),
        "dates": json.loads(draft.dates_json),
        "offices": json.loads(draft.offices_json),
        "chunks": chunks,
        "status": draft.status,
    }

@app.get("/admin/kb/drafts")
def kb_list_drafts(request: Request):
    require_admin(request)
    drafts = list_drafts()
    return [
        {
            "id": d.id,
            "file_name": d.file_name,
            "scholarship_name": d.scholarship_name,
            "kind": getattr(d, "kind", "scholarship"),
            "year": d.year,
            "version": d.version,
            "required_documents": json.loads(d.required_documents_json),
            "dates": json.loads(d.dates_json),
            "offices": json.loads(d.offices_json),
            "chunks_count": len(json.loads(d.chunks_json)),
            "status": d.status,
            "created_at": str(d.created_at) if hasattr(d, "created_at") else "",
        }
        for d in drafts
    ]

@app.get("/admin/kb/{draft_id}")
def kb_get_draft(draft_id: int, request: Request):
    require_admin(request)
    d = get_draft(draft_id)
    if not d:
        raise HTTPException(status_code=404, detail="Draft not found")
    return {
        "id": d.id,
        "file_name": d.file_name,
        "scholarship_name": d.scholarship_name,
        "kind": getattr(d, "kind", "scholarship"),
        "year": d.year,
        "version": d.version,
        "required_documents": json.loads(d.required_documents_json),
        "dates": json.loads(d.dates_json),
        "offices": json.loads(d.offices_json),
        "chunks": json.loads(d.chunks_json),
        "status": d.status,
    }

@app.post("/admin/kb/{draft_id}/publish")
def kb_publish(draft_id: int, request: Request, payload: PublishPayload = None):
    require_admin(request)
    updates = payload.model_dump(exclude_none=True) if payload else None
    try:
        res = publish_draft(draft_id, updates)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/admin/kb/{draft_id}")
def kb_delete(draft_id: int, request: Request):
    require_admin(request)
    res = delete_draft(draft_id)
    return res

# --- Admin Data Management & Bulk Import Endpoints (Token Protected) ---

class SettingPayload(BaseModel):
    text: str

@app.get("/api/admin/crud/{table}")
def admin_list_table(table: str, request: Request):
    require_admin(request)
    try:
        return list_table_rows(table)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/admin/crud/{table}")
def admin_create_row(table: str, data: dict, request: Request):
    require_admin(request)
    try:
        return create_table_row(table, data, who="admin")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Creation failed: {str(e)}")

@app.put("/api/admin/crud/{table}/{row_id}")
def admin_update_row(table: str, row_id: int, data: dict, request: Request):
    require_admin(request)
    try:
        return update_table_row(table, row_id, data, who="admin")
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Update failed: {str(e)}")

@app.delete("/api/admin/crud/{table}/{row_id}")
def admin_delete_row(table: str, row_id: int, request: Request):
    require_admin(request)
    try:
        success = delete_table_row(table, row_id, who="admin")
        if not success:
            raise HTTPException(status_code=404, detail=f"Row {row_id} not found in {table}")
        return {"status": "ok", "deleted_id": row_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/admin/settings/deadline-banner")
def admin_get_deadline_banner(request: Request):
    require_admin(request)
    return {"text": get_setting("deadline_banner", "Applications close Tonight, 11:59 PM. Verify all required documents!")}

@app.post("/api/admin/settings/deadline-banner")
def admin_set_deadline_banner(payload: SettingPayload, request: Request):
    require_admin(request)
    set_setting("deadline_banner", payload.text)
    add_audit_log("admin", f"Updated deadline banner to: '{payload.text}'")
    return {"status": "ok", "text": payload.text}

@app.get("/api/admin/audit-logs")
def admin_get_audit_logs_endpoint(request: Request, limit: int = 100):
    require_admin(request)
    return get_audit_logs(limit=limit)

@app.post("/admin/import/{table}")
@app.post("/api/admin/import/{table}")
async def admin_import_file(table: str, request: Request, file: UploadFile = File(...), commit: bool = False):
    require_admin(request)
    content = await file.read()
    filename = file.filename or "import_data.csv"
    try:
        raw_rows = parse_import_file(content, filename)
        preview_res = validate_and_preview(table, raw_rows)
        if not commit:
            return {
                "status": "preview",
                "table": table,
                "filename": filename,
                "total_rows": preview_res["total_rows"],
                "valid_count": preview_res["valid_count"],
                "error_count": preview_res["error_count"],
                "errors": preview_res["errors"],
                "sample": preview_res["preview_sample"],
            }
        else:
            if not preview_res["valid_rows"]:
                raise HTTPException(status_code=400, detail="No valid rows to commit. Please check file errors.")
            saved_count = commit_import_rows(table, preview_res["valid_rows"], who="admin")
            return {
                "status": "committed",
                "table": table,
                "filename": filename,
                "saved_count": saved_count,
                "error_count": preview_res["error_count"],
                "errors": preview_res["errors"],
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process import: {str(e)}")
