"""Authentication service for Students and Admin.
Handles password/PIN hashing, session token creation, and validation.
"""
import hashlib
import os
import secrets
from datetime import datetime, timezone
from typing import Optional
from src.database.db import conn, get_session
from src.database.models import Student

# In-memory fast cache for active sessions (token -> {"user_id": str, "role": str})
_SESSIONS: dict[str, dict] = {}

def hash_pin(pin: str) -> str:
    """Hash PIN using PBKDF2-HMAC-SHA256 with a unique salt."""
    if len(pin) < 4:
        raise ValueError("PIN must be at least 4 digits")
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"pbkdf2_sha256${salt}${key.hex()}"

def verify_pin(pin: str, hashed: str) -> bool:
    """Verify plain PIN against stored PBKDF2 hash."""
    if not hashed or "$" not in hashed:
        return False
    try:
        algorithm, salt, stored_hash = hashed.split("$", 2)
        if algorithm != "pbkdf2_sha256":
            return False
        key = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return secrets.compare_digest(key.hex(), stored_hash)
    except Exception:
        return False

def init_auth_tables():
    """Ensure sessions table and student columns exist in SQLite."""
    with conn() as c:
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

        # Seed default PIN for demo students if their pin_hash is empty
        # Default demo PIN is "1234"
        demo_pin_hash = hash_pin("1234")
        c.execute("UPDATE students SET pin_hash=? WHERE pin_hash='' OR pin_hash IS NULL", (demo_pin_hash,))
        c.commit()

def create_student_session(student_id: str) -> str:
    """Create and persist a session token for a student."""
    init_auth_tables()
    token = secrets.token_urlsafe(32)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO user_sessions (token, user_id, role, created_at) VALUES (?, ?, 'student', ?)",
                  (token, student_id, now_str))
        c.commit()
    _SESSIONS[token] = {"user_id": student_id, "role": "student"}
    return token

def create_admin_session() -> str:
    """Create and persist a session token for an admin."""
    init_auth_tables()
    token = secrets.token_urlsafe(32)
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO user_sessions (token, user_id, role, created_at) VALUES (?, 'admin', 'admin', ?)",
                  (token, now_str))
        c.commit()
    _SESSIONS[token] = {"user_id": "admin", "role": "admin"}
    return token

def get_session_info(token: str) -> Optional[dict]:
    """Look up session info from memory cache or database."""
    if not token:
        return None
    token = token.strip()
    if token.startswith("Bearer "):
        token = token[7:].strip()

    if token in _SESSIONS:
        return _SESSIONS[token]

    init_auth_tables()
    with conn() as c:
        row = c.execute("SELECT user_id, role FROM user_sessions WHERE token=?", (token,)).fetchone()
        if row:
            info = {"user_id": row["user_id"], "role": row["role"]}
            _SESSIONS[token] = info
            return info
    return None

def get_student_id_from_token(token: str) -> Optional[str]:
    """Return student_id if token is a valid student session."""
    info = get_session_info(token)
    if info and info["role"] == "student":
        return info["user_id"]
    return None

def verify_admin_token(token: str) -> bool:
    """Check if token is a valid admin session."""
    info = get_session_info(token)
    return bool(info and info["role"] == "admin")

def verify_admin_passcode(passcode: str) -> bool:
    """Verify admin passcode against ADMIN_PASSCODE env var."""
    admin_passcode = os.getenv("ADMIN_PASSCODE", "nimbus_admin_2026").strip()
    if not passcode:
        return False
    return secrets.compare_digest(passcode.strip(), admin_passcode)

def register_student(student_id: str, name: str, branch: str, year: str, category: str, language: str, pin: str) -> tuple[bool, str, Optional[str]]:
    """Register a new student with hashed PIN."""
    init_auth_tables()
    student_id = student_id.strip()
    if not student_id:
        return False, "Student ID cannot be empty", None
    if len(pin) < 4:
        return False, "PIN must be at least 4 digits", None

    with get_session() as session:
        existing = session.get(Student, student_id)
        if existing:
            return False, f"Student ID '{student_id}' is already registered", None

        hashed = hash_pin(pin)
        student = Student(
            student_id=student_id,
            name=name.strip(),
            branch=branch.strip(),
            year=year.strip(),
            category=category.strip() or "General",
            language=language.strip() or "English",
            pin_hash=hashed,
            scholarship="",
        )
        session.add(student)
        session.commit()

    token = create_student_session(student_id)
    return True, "Registration successful", token

def authenticate_student(student_id: str, pin: str) -> tuple[bool, str, Optional[str]]:
    """Authenticate student ID and PIN, returning session token on success."""
    init_auth_tables()
    student_id = student_id.strip()
    with get_session() as session:
        student = session.get(Student, student_id)
        if not student:
            return False, "Invalid Student ID or PIN", None
        if not verify_pin(pin, student.pin_hash):
            return False, "Invalid Student ID or PIN", None

    token = create_student_session(student_id)
    return True, "Login successful", token
