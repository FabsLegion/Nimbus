import pytest
from fastapi.testclient import TestClient
from api import app
from src.database.db import conn
from src.services.auth import (
    register_student,
    authenticate_student,
    hash_pin,
    verify_pin,
    verify_admin_passcode,
    create_admin_session,
)

client = TestClient(app)

def test_pin_hashing_and_verification():
    pin = "5432"
    hashed = hash_pin(pin)
    assert hashed != pin
    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_pin(pin, hashed) is True
    assert verify_pin("0000", hashed) is False
    assert verify_pin("54321", hashed) is False

def test_portal_html_routes():
    # 1. Landing page route /
    landing = client.get("/")
    assert landing.status_code == 200
    assert "Student Portal" in landing.text
    assert "Office Portal" in landing.text
    # Ensure no old dropdowns
    assert 'select id="sid"' not in landing.text

    # 2. Student portal page /student
    stu = client.get("/student")
    assert stu.status_code == 200
    assert "Sign In" in stu.text
    assert "Create Account" in stu.text
    assert "Security PIN" in stu.text
    assert 'select id="sid"' not in stu.text

    # 3. Admin portal page /admin
    adm = client.get("/admin")
    assert adm.status_code == 200
    assert "Security Passcode" in adm.text
    assert "Knowledge Base" in adm.text

def test_end_to_end_student_lifecycle_and_admin_view():
    """Test full requested user flow:
    Create an account, sign in, choose a scholarship, upload a document,
    ask a question (RAG + Open chat with memory), sign in to /admin and find the case.
    """
    test_sid = "STU_E2E_99"
    test_pin = "8899"

    # Clean up any previous test student
    with conn() as c:
        c.execute("DELETE FROM students WHERE student_id=?", (test_sid,))
        c.execute("DELETE FROM documents WHERE student_id=?", (test_sid,))
        c.execute("DELETE FROM queries WHERE student_id=?", (test_sid,))
        c.execute("DELETE FROM chat_messages WHERE student_id=?", (test_sid,))
        c.execute("DELETE FROM applications WHERE student_id=?", (test_sid,))
        c.commit()

    # 1. Create an account via API
    reg_resp = client.post("/api/auth/register", json={
        "student_id": test_sid,
        "name": "Jordan Lee",
        "branch": "Computer Science",
        "year": "3rd Year",
        "category": "OBC",
        "language": "English",
        "pin": test_pin,
    })
    assert reg_resp.status_code == 200, reg_resp.text
    reg_data = reg_resp.json()
    assert "token" in reg_data
    token = reg_data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify student is in DB with hashed PIN (never plain text)
    with conn() as c:
        row = c.execute("SELECT pin_hash FROM students WHERE student_id=?", (test_sid,)).fetchone()
        assert row is not None
        assert test_pin not in row["pin_hash"]
        assert row["pin_hash"].startswith("pbkdf2_sha256$")

    # 2. Sign in via API
    login_resp = client.post("/api/auth/login", json={
        "student_id": test_sid,
        "pin": test_pin,
    })
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert login_data["student"]["name"] == "Jordan Lee"
    token = login_data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Choose a scholarship
    choose_resp = client.post("/api/scholarship/choose", json={
        "scholarship": "Merit Scholarship - Undergraduate"
    }, headers=headers)
    assert choose_resp.status_code == 200

    # Verify state endpoint uses token, not student_id from browser
    state_resp = client.get("/api/state", headers=headers)
    assert state_resp.status_code == 200
    state_data = state_resp.json()
    assert state_data["student"]["student_id"] == test_sid
    assert state_data["scholarship"] == "Merit Scholarship - Undergraduate"
    assert len(state_data["checklist"]) == 4

    # 4. Upload a document
    upload_resp = client.post("/api/upload", json={
        "doc_type": "Identity Proof",
        "file_name": "aadhaar_card_jordan.pdf"
    }, headers=headers)
    assert upload_resp.status_code == 200

    # Verify checklist updated for this student
    state_after_upload = client.get("/api/state", headers=headers).json()
    id_doc = next(item for item in state_after_upload["checklist"] if item[0] == "Identity Proof")
    assert id_doc[1] == "OK"

    # 5. Ask questions:
    # A) RAG question
    chat_rag = client.post("/api/chat", json={
        "message": "What is the requirement for Income Certificate?"
    }, headers=headers)
    assert chat_rag.status_code == 200
    rag_data = chat_rag.json()
    assert len(rag_data["answer"]) > 0

    # B) Open chat question outside scholarship rules -> answered by LLM, labeled "General answer, not from scholarship documents"
    chat_open = client.post("/api/chat", json={
        "message": "Can you recommend good study strategies for midterm exams?"
    }, headers=headers)
    assert chat_open.status_code == 200
    open_data = chat_open.json()
    assert "General answer, not from scholarship documents" in open_data["answer"] or open_data.get("label") == "General answer, not from scholarship documents"

    # Verify chat messages were stored in chat_messages table
    with conn() as c:
        msgs = c.execute("SELECT role, content FROM chat_messages WHERE student_id=?", (test_sid,)).fetchall()
        assert len(msgs) >= 4  # 2 user questions + 2 assistant replies

    # 6. Sign in to /admin and find the case
    # Unauthenticated /api/admin must be rejected
    unauth_admin = client.get("/api/admin")
    assert unauth_admin.status_code == 401

    # Login as admin
    admin_login_resp = client.post("/api/auth/admin-login", json={
        "passcode": "nimbus_admin_2026"
    })
    assert admin_login_resp.status_code == 200
    admin_token = admin_login_resp.json()["token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Fetch admin overview and verify student's queries / document problems appear
    admin_data_resp = client.get("/api/admin", headers=admin_headers)
    assert admin_data_resp.status_code == 200
    admin_info = admin_data_resp.json()
    assert admin_info["total"] > 0
    # Jordan's missing documents (e.g. Income Certificate, Marksheet, Bank Document) are in problems queue
    jordan_problems = [p for p in admin_info["problems"] if p["student"] == test_sid]
    assert len(jordan_problems) >= 1
    assert any(p["document"] in ["Income Certificate", "Marksheet", "Bank Document"] for p in jordan_problems)
