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

def get_offices() -> dict[str, str]:
    """Return map of category -> office name from offices table."""
    with get_session() as session:
        offices = session.exec(select(Office)).all()
        return {o.category: o.name for o in offices}

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
