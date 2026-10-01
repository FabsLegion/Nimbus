"""Seed script to load initial data into SQLModel tables."""
import json
import random
from sqlmodel import select
from src.database.db import get_session, init, conn
from src.database.models import (
    Scholarship,
    RequiredDocument,
    TimelineEvent,
    Office,
    Student,
    StudentDocument,
    Setting,
    QueryLog,
)

def seed():
    init()
    session = get_session()

    # 1. Scholarships
    scholarships_data = [
        ("Merit Scholarship - Undergraduate", "Merit-based scholarship for undergraduate engineering and science students.", 2026, 3),
        ("Merit Scholarship - Special Category", "Merit-based scholarship for special category students.", 2026, 2),
    ]
    for name, desc, yr, ver in scholarships_data:
        if not session.exec(select(Scholarship).where(Scholarship.name == name)).first():
            session.add(Scholarship(name=name, description=desc, year=yr, version=ver))

    # 2. Required Documents
    reqs_data = [
        ("Merit Scholarship - Undergraduate", ["Identity Proof", "Income Certificate", "Marksheet", "Bank Document"]),
        ("Merit Scholarship - Special Category", ["Identity Proof", "Category Certificate", "Marksheet"]),
    ]
    for sch_name, docs in reqs_data:
        for doc in docs:
            exists = session.exec(select(RequiredDocument).where(
                RequiredDocument.scholarship_name == sch_name,
                RequiredDocument.doc_type == doc
            )).first()
            if not exists:
                session.add(RequiredDocument(scholarship_name=sch_name, doc_type=doc))

    # 3. Timeline Events
    timeline_data = [
        ("deadline", "Application Deadline", "Tonight, 11:59 PM", 1),
        ("verification", "Document Verification", "03 Oct to 07 Oct", 2),
        ("results", "Results Announcement", "10 Oct", 3),
        ("next_round", "Next Round", "12 Oct", 4),
        ("allotment", "Seat Allotment", "15 Oct", 5),
        ("classes", "Classes Commence", "20 Oct", 6),
    ]
    for key, title, dt, order in timeline_data:
        existing = session.exec(select(TimelineEvent).where(TimelineEvent.event_key == key)).first()
        if not existing:
            session.add(TimelineEvent(event_key=key, title=title, date_str=dt, order_num=order))

    # 4. Offices & Routing Keywords (The OFFICE map: unanswerable from scholarship rules)
    offices_data = [
        ("PAYMENT", "Scholarship / Finance Office", "scholarships@univ.edu", "080-12345678", "Disbursements and stipend issues", "payment,credited,not received,money"),
        ("PORTAL", "IT Helpdesk", "it-support@univ.edu", "080-23456789", "Portal login and website glitches", "portal crash,login,not loading,website"),
        ("HOSTEL", "Hostel Office", "hostel@univ.edu", "080-34567890", "Hostel accommodation and mess facilities", "hostel"),
        ("FEES", "Accounts Section", "accounts@univ.edu", "080-45678901", "College tuition fee inquiries", "fee"),
    ]
    # Remove any extra offices from previous seed runs
    for o in session.exec(select(Office)).all():
        if o.category not in ["PAYMENT", "PORTAL", "HOSTEL", "FEES"]:
            session.delete(o)
    for cat, name, email, phone, desc, kw in offices_data:
        existing = session.exec(select(Office).where(Office.category == cat)).first()
        if not existing:
            session.add(Office(category=cat, name=name, email=email, phone=phone, description=desc, routing_keywords=kw))
        else:
            existing.routing_keywords = kw

    # 5. Settings: Document Keywords and Query Rules
    doc_kw = {
        "income": "Income Certificate",
        "caste": "Caste Certificate",
        "category": "Category Certificate",
        "marksheet": "Marksheet",
        "aadhaar": "Identity Proof",
        "bank": "Bank Document",
    }
    existing_setting = session.exec(select(Setting).where(Setting.key == "doc_keywords")).first()
    if not existing_setting:
        session.add(Setting(key="doc_keywords", value=json.dumps(doc_kw)))

    query_rules = [
        ["DEADLINE", ["deadline", "last date"]],
        ["VERIFICATION", ["verification", "verified"]],
        ["RESULT", ["result"]],
        ["DOCUMENT", ["document", "certificate", "upload", "missing", "marksheet"]],
    ]
    existing_rules_setting = session.exec(select(Setting).where(Setting.key == "query_rules")).first()
    if not existing_rules_setting:
        session.add(Setting(key="query_rules", value=json.dumps(query_rules)))
    else:
        existing_rules_setting.value = json.dumps(query_rules)

    # 6. Students
    M = "Merit Scholarship - Undergraduate"
    students_data = [
        ("STU001", "Demo Student", "Computer Science", "2nd Year", "English", ""),
        ("STU002", "Priya", "Electronics", "2nd Year", "English", M),
        ("STU003", "Arjun", "Mechanical", "3rd Year", "English", M),
        ("STU004", "Kavya", "Civil", "2nd Year", "Kannada", M),
    ]
    for sid, name, branch, yr, lang, sch in students_data:
        if not session.exec(select(Student).where(Student.student_id == sid)).first():
            session.add(Student(student_id=sid, name=name, branch=branch, year=yr, language=lang, scholarship=sch))

    # 7. Student Documents
    docs_data = [
        ("STU001", "Identity Proof", "aadhaar.pdf", "ok", ""),
        ("STU001", "Marksheet", "marksheet_sem3.pdf", "ok", ""),
        ("STU001", "Income Certificate", "income_certificate_2025.pdf", "invalid", "Certificate is from 2025; a current-year certificate is required"),
        ("STU002", "Identity Proof", "aadhaar.pdf", "ok", ""),
        ("STU002", "Marksheet", "marksheet.pdf", "ok", ""),
        ("STU002", "Bank Document", "bank_passbook.pdf", "ok", ""),
        ("STU002", "Caste Certificate", "income_certificate_2026.pdf", "ok", ""),
        ("STU003", "Identity Proof", "aadhaar.pdf", "ok", ""),
        ("STU003", "Income Certificate", "income_2026.pdf", "ok", ""),
        ("STU003", "Marksheet", "marksheet.pdf", "ok", ""),
        ("STU003", "Bank Document", "bank.pdf", "ok", ""),
        ("STU004", "Identity Proof", "aadhaar.pdf", "ok", ""),
        ("STU004", "Marksheet", "marksheet.pdf", "ok", ""),
    ]
    for sid, doc_type, fn, status, reason in docs_data:
        exists = session.exec(select(StudentDocument).where(
            StudentDocument.student_id == sid,
            StudentDocument.doc_type == doc_type
        )).first()
        if not exists:
            session.add(StudentDocument(student_id=sid, doc_type=doc_type, file_name=fn, status=status, reason=reason))

    # 8. Sample Queries
    if not session.exec(select(QueryLog)).first():
        cats = ["DOCUMENT"] * 13 + ["SCHOLARSHIP"] * 9 + ["DEADLINE"] * 6 + ["VERIFICATION"] * 6 + ["PAYMENT"] * 3
        for cat in cats:
            sid = f"STU00{random.randint(1, 4)}"
            resolved = 0 if cat == "PAYMENT" else 1
            office = "Scholarship / Finance Office" if cat == "PAYMENT" else ""
            session.add(QueryLog(student_id=sid, category=cat, text="sample question", resolved=resolved, office=office))

    session.commit()
    session.close()

    # Also synchronize the legacy 'documents' table
    c = conn()
    c.execute("DELETE FROM documents")
    for sid, doc_type, fn, status, reason in docs_data:
        c.execute("INSERT INTO documents(student_id,doc_type,file_name,status,reason) VALUES (?,?,?,?,?)",
                  (sid, doc_type, fn, status, reason))
    c.commit()
    print("Database seeded")

if __name__ == "__main__":
    seed()
