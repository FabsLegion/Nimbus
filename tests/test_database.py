from src.database.db import (
    get_catalog,
    get_required_documents,
    get_timeline,
    get_offices,
    get_routing_rules,
    conn,
)
from src.services.checklist import checklist

def test_database_tables_exist():
    expected_tables = {
        "scholarships",
        "required_documents",
        "timeline_events",
        "offices",
        "students",
        "applications",
        "student_documents",
        "chat_sessions",
        "chat_messages",
        "tickets",
        "notifications",
        "queries",
        "settings",
    }
    with conn() as c:
        rows = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        existing = {r["name"] for r in rows}
    assert expected_tables.issubset(existing), f"Missing tables: {expected_tables - existing}"

def test_database_catalog_and_reqs():
    catalog = get_catalog()
    assert "Merit Scholarship - Undergraduate" in catalog
    assert "Merit Scholarship - Special Category" in catalog

    reqs = get_required_documents("Merit Scholarship - Undergraduate")
    assert "Identity Proof" in reqs
    assert "Income Certificate" in reqs
    assert "Marksheet" in reqs
    assert "Bank Document" in reqs

def test_database_timeline_and_offices():
    timeline = get_timeline()
    assert "deadline" in timeline
    assert "verification" in timeline
    assert timeline["deadline"] == "Tonight, 11:59 PM"

    offices = get_offices()
    assert "PAYMENT" in offices
    assert "PORTAL" in offices

    rules = get_routing_rules()
    assert any(cat == "PAYMENT" and "payment" in words for cat, words in rules)

def test_checklist_from_database():
    items = checklist("STU001", "Merit Scholarship - Undergraduate")
    assert len(items) == 4
    names = [i[0] for i in items]
    assert "Identity Proof" in names
    assert "Bank Document" in names
