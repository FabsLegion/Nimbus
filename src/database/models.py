"""Database models defined with SQLModel for the Nimbus application."""
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field

class Scholarship(SQLModel, table=True):
    __tablename__ = "scholarships"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    description: Optional[str] = ""
    year: Optional[int] = 2026
    version: Optional[int] = 1

class RequiredDocument(SQLModel, table=True):
    __tablename__ = "required_documents"
    id: Optional[int] = Field(default=None, primary_key=True)
    scholarship_name: str = Field(index=True)
    doc_type: str
    description: Optional[str] = ""

class TimelineEvent(SQLModel, table=True):
    __tablename__ = "timeline_events"
    id: Optional[int] = Field(default=None, primary_key=True)
    event_key: str = Field(index=True, unique=True)
    title: str
    date_str: str
    order_num: int = 0

class Office(SQLModel, table=True):
    __tablename__ = "offices"
    id: Optional[int] = Field(default=None, primary_key=True)
    category: str = Field(index=True, unique=True)
    name: str
    email: Optional[str] = ""
    phone: Optional[str] = ""
    description: Optional[str] = ""
    routing_keywords: str = ""

class Student(SQLModel, table=True):
    __tablename__ = "students"
    student_id: str = Field(primary_key=True)
    name: str
    branch: str
    year: str
    language: str
    category: Optional[str] = Field(default="General")
    pin_hash: Optional[str] = Field(default="")
    scholarship: str = ""

class Application(SQLModel, table=True):
    __tablename__ = "applications"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    scholarship_name: str
    status: str = "submitted"
    submitted_at: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

class StudentDocument(SQLModel, table=True):
    __tablename__ = "student_documents"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    doc_type: str
    file_name: str
    status: str = "ok"
    reason: Optional[str] = ""
    detected_type: Optional[str] = None
    detected_year: Optional[int] = None
    uploaded_at: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

class ChatSession(SQLModel, table=True):
    __tablename__ = "chat_sessions"
    id: str = Field(primary_key=True)
    student_id: str = Field(index=True)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    student_id: str = Field(index=True)
    role: str
    content: str
    metadata_json: Optional[str] = "{}"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    category: str
    subject: str
    description: str
    status: str = "open"
    office: str
    created_at: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

class Notification(SQLModel, table=True):
    __tablename__ = "notifications"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    priority: str
    message: str
    ts: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

class QueryLog(SQLModel, table=True):
    __tablename__ = "queries"
    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    category: str
    text: str
    resolved: int = 1
    office: Optional[str] = ""
    ts: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

class Setting(SQLModel, table=True):
    __tablename__ = "settings"
    key: str = Field(primary_key=True)
    value: str

class KnowledgeDraft(SQLModel, table=True):
    __tablename__ = "knowledge_drafts"
    id: Optional[int] = Field(default=None, primary_key=True)
    file_name: str
    scholarship_name: str
    year: int = 2026
    version: int = 1
    required_documents_json: str = "[]"
    dates_json: str = "{}"
    offices_json: str = "[]"
    chunks_json: str = "[]"
    status: str = "draft"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))

