"""Database connection, session management, and data access helpers."""
import sqlite3
import json
from sqlmodel import SQLModel, create_engine, Session, select
from src.database.models import (
    Scholarship,
    RequiredDocument,
    TimelineEvent,
    Office,
    Student,
    Application,
    StudentDocument,
    ChatSession,
    ChatMessage,
    Ticket,
    Notification,
    QueryLog,
    Setting,
    KnowledgeDraft,
    ScholarshipFact,
    Announcement,
    AuditLog,
)

DB_FILE = "app.db"
DATABASE_URL = f"sqlite:///{DB_FILE}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

def conn():
    """Return raw sqlite3 connection with Row factory for compatibility."""
    c = sqlite3.connect(DB_FILE)
    c.row_factory = sqlite3.Row
    return c

def get_session():
    """Return a new SQLModel session."""
    return Session(engine)

def init():
    """Create all tables with SQLModel without dropping existing tables."""
    SQLModel.metadata.create_all(engine)
    # Ensure legacy 'documents' table/view compatibility for student_documents
    with conn() as c:
        c.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT,
            doc_type TEXT,
            file_name TEXT,
            status TEXT,
            reason TEXT
        )
        """)
        c.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            token TEXT PRIMARY KEY,
            user_id TEXT,
            role TEXT,
            created_at TEXT
        )
        """)
        cols = {row["name"] for row in c.execute("PRAGMA table_info(students)").fetchall()}
        if "category" not in cols:
            c.execute("ALTER TABLE students ADD COLUMN category TEXT DEFAULT 'General'")
        if "pin_hash" not in cols:
            c.execute("ALTER TABLE students ADD COLUMN pin_hash TEXT DEFAULT ''")
        c.commit()

    # Seed default scholarship facts, announcements, and deadline banner if empty
    with get_session() as session:
        if not session.exec(select(ScholarshipFact)).first():
            default_facts = [
                ScholarshipFact(scholarship_id="Merit Scholarship - Undergraduate", label="Fee Reduction", value="75% Tuition Fee Waiver", sort_order=1),
                ScholarshipFact(scholarship_id="Merit Scholarship - Undergraduate", label="Monthly Stipend", value="Rs 4,000 / month", sort_order=2),
                ScholarshipFact(scholarship_id="Merit Scholarship - Undergraduate", label="Eligibility Criteria", value="CGPA >= 8.5 with no active backlogs", sort_order=3),
                ScholarshipFact(scholarship_id="Merit Scholarship - Special Category", label="Fee Reduction", value="100% Tuition Fee Waiver", sort_order=1),
                ScholarshipFact(scholarship_id="Merit Scholarship - Special Category", label="Monthly Stipend", value="Rs 6,000 / month", sort_order=2),
                ScholarshipFact(scholarship_id="Need-Based Financial Assistance Scholarship", label="Fee Reduction", value="50% Tuition Fee Waiver", sort_order=1),
                ScholarshipFact(scholarship_id="Need-Based Financial Assistance Scholarship", label="Stipend Amount", value="Rs 50,000 annual grant", sort_order=2),
                ScholarshipFact(scholarship_id="Need-Based Financial Assistance Scholarship", label="Income Ceiling", value="Under Rs 4,00,000 per annum", sort_order=3),
            ]
            for f in default_facts:
                session.add(f)
            session.commit()

        if not session.exec(select(Announcement)).first():
            session.add(Announcement(
                title="Application Verification Window Opens Soon",
                body="Physical and digital verification of certificates will begin October 3rd. Keep your documents in order.",
                priority="INFORMATIONAL",
                active=1
            ))
            session.commit()

        if not session.exec(select(Setting).where(Setting.key == "deadline_banner")).first():
            session.add(Setting(key="deadline_banner", value="Applications close Tonight, 11:59 PM. Verify all required documents!"))
            session.commit()

# --- Database Access Helpers (replacing hardcoded structures) ---

def get_catalog() -> list[str]:
    """Return list of available scholarship names from the database."""
    with get_session() as session:
        return [s.name for s in session.exec(select(Scholarship)).all()]

def get_required_documents(scholarship_name: str) -> list[str]:
    """Return list of required document types for a scholarship from the database."""
    with get_session() as session:
        stmt = select(RequiredDocument.doc_type).where(RequiredDocument.scholarship_name == scholarship_name)
        return list(session.exec(stmt).all())

def get_all_required_documents() -> dict[str, list[str]]:
    """Return map of scholarship_name -> required document types."""
    with get_session() as session:
        records = session.exec(select(RequiredDocument)).all()
        out: dict[str, list[str]] = {}
        for r in records:
            out.setdefault(r.scholarship_name, []).append(r.doc_type)
        return out

def get_timeline() -> dict[str, str]:
    """Return timeline dates dictionary from timeline_events table."""
    with get_session() as session:
        events = session.exec(select(TimelineEvent).order_by(TimelineEvent.order_num)).all()
        return {e.event_key: e.date_str for e in events}

def get_timeline_list() -> list[dict]:
    """Return timeline events ordered by order_num."""
    with get_session() as session:
        events = session.exec(select(TimelineEvent).order_by(TimelineEvent.order_num)).all()
        return [{"id": e.id, "event_key": e.event_key, "title": e.title, "date_str": e.date_str, "order_num": e.order_num} for e in events]

def get_offices() -> dict[str, str]:
    """Return map of category -> office name from offices table."""
    with get_session() as session:
        offices = session.exec(select(Office)).all()
        return {o.category: o.name for o in offices}

def get_offices_list() -> list[dict]:
    """Return all offices with contact details."""
    with get_session() as session:
        offices = session.exec(select(Office)).all()
        return [
            {
                "id": o.id,
                "category": o.category,
                "name": o.name,
                "email": o.email or "",
                "phone": o.phone or "",
                "description": o.description or "",
                "routing_keywords": o.routing_keywords or "",
            }
            for o in offices
        ]

def get_routing_rules() -> list[tuple[str, list[str]]]:
    """Return list of (category, [keywords]) from offices table and settings."""
    with get_session() as session:
        offices = session.exec(select(Office)).all()
        rules = []
        for o in offices:
            words = [w.strip() for w in o.routing_keywords.split(",") if w.strip()]
            rules.append((o.category, words))
        # Additional query categories
        setting = session.exec(select(Setting).where(Setting.key == "query_rules")).first()
        if setting:
            try:
                for cat, words in json.loads(setting.value):
                    rules.append((cat, words))
            except Exception:
                pass
        return rules

def get_doc_keywords() -> dict[str, str]:
    """Return keyword -> doc_type mapping stored in settings table."""
    with get_session() as session:
        setting = session.exec(select(Setting).where(Setting.key == "doc_keywords")).first()
        if setting:
            try:
                return json.loads(setting.value)
            except Exception:
                pass
        return {}

def get_scholarship_facts(scholarship_id: str = None) -> list[dict]:
    """Return scholarship facts ordered by sort_order."""
    with get_session() as session:
        stmt = select(ScholarshipFact)
        if scholarship_id:
            stmt = stmt.where(ScholarshipFact.scholarship_id == scholarship_id)
        stmt = stmt.order_by(ScholarshipFact.sort_order, ScholarshipFact.id)
        facts = session.exec(stmt).all()
        return [{"id": f.id, "scholarship_id": f.scholarship_id, "label": f.label, "value": f.value, "sort_order": f.sort_order} for f in facts]

def get_announcements(active_only: bool = True) -> list[dict]:
    """Return announcements from database."""
    with get_session() as session:
        stmt = select(Announcement)
        if active_only:
            stmt = stmt.where(Announcement.active == 1)
        stmt = stmt.order_by(Announcement.id.desc())
        anns = session.exec(stmt).all()
        return [{"id": a.id, "title": a.title, "body": a.body, "priority": a.priority, "active": a.active, "created_at": a.created_at} for a in anns]

def add_audit_log(who: str, what: str) -> None:
    """Record administrative modification or import in audit_log."""
    try:
        with get_session() as session:
            entry = AuditLog(who=who or "admin", what=what)
            session.add(entry)
            session.commit()
    except Exception:
        pass

def get_audit_logs(limit: int = 100) -> list[dict]:
    """Retrieve audit log entries."""
    with get_session() as session:
        stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
        logs = session.exec(stmt).all()
        return [{"id": l.id, "who": l.who, "what": l.what, "when": l.when_ts} for l in logs]

def get_setting(key: str, default: str = "") -> str:
    """Get a configuration value from settings table."""
    with get_session() as session:
        s = session.exec(select(Setting).where(Setting.key == key)).first()
        return s.value if s else default

def set_setting(key: str, value: str) -> None:
    """Set or update a configuration value in settings table."""
    with get_session() as session:
        s = session.exec(select(Setting).where(Setting.key == key)).first()
        if s:
            s.value = str(value)
        else:
            session.add(Setting(key=key, value=str(value)))
        session.commit()

# Ensure schema tables and initial seeds exist
init()
