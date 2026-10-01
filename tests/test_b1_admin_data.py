"""Test suite for Task B1: Admin data management, bulk imports, dynamic facts, and audit logging."""
import io
import os
import pytest
from fastapi.testclient import TestClient
from api import app
from src.database.db import (
    conn,
    get_scholarship_facts,
    get_announcements,
    get_audit_logs,
    get_setting,
    set_setting,
)
from src.services.assistant import answer
from src.services.auth import create_admin_session, register_student, authenticate_student

client = TestClient(app)

@pytest.fixture
def admin_headers():
    token = create_admin_session()
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def student_auth():
    sid = "STU_B1_TEST"
    success, msg, token = register_student(
        student_id=sid,
        name="Aarav Sharma",
        branch="Computer Science",
        year="1st Year",
        category="General",
        language="English",
        pin="1234",
    )
    if not success or not token:
        success, msg, token = authenticate_student(sid, "1234")
    return {"student_id": sid, "token": token, "headers": {"Authorization": f"Bearer {token}"}}


def test_b1_database_defaults():
    facts = get_scholarship_facts("Merit Scholarship - Undergraduate")
    assert len(facts) >= 3
    fee_fact = next((f for f in facts if "Fee Reduction" in f["label"]), None)
    assert fee_fact is not None

    anns = get_announcements(active_only=True)
    assert len(anns) >= 1

    banner = get_setting("deadline_banner")
    assert len(banner) > 5


def test_b1_bulk_import_scholarships_preview_and_commit(admin_headers):
    csv_path = "nimbus-samples/admin_imports/scholarships.csv"
    assert os.path.exists(csv_path)
    with open(csv_path, "rb") as f:
        file_bytes = f.read()

    # Preview mode
    res_preview = client.post(
        "/admin/import/scholarships?commit=false",
        headers=admin_headers,
        files={"file": ("scholarships.csv", io.BytesIO(file_bytes), "text/csv")},
    )
    assert res_preview.status_code == 200
    pdata = res_preview.json()
    assert pdata["status"] == "preview"
    assert pdata["valid_count"] >= 3
    assert pdata["error_count"] == 0

    # Commit mode
    res_commit = client.post(
        "/admin/import/scholarships?commit=true",
        headers=admin_headers,
        files={"file": ("scholarships.csv", io.BytesIO(file_bytes), "text/csv")},
    )
    assert res_commit.status_code == 200
    cdata = res_commit.json()
    assert cdata["status"] == "committed"
    assert cdata["saved_count"] >= 3

    # Check audit log
    logs = get_audit_logs(limit=5)
    assert any("bulk imported" in l["what"].lower() and "scholarships" in l["what"].lower() for l in logs)


def test_b1_bulk_import_timeline_events_commit(admin_headers):
    csv_path = "nimbus-samples/admin_imports/timeline_events.csv"
    assert os.path.exists(csv_path)
    with open(csv_path, "rb") as f:
        file_bytes = f.read()

    res_commit = client.post(
        "/admin/import/timeline_events?commit=true",
        headers=admin_headers,
        files={"file": ("timeline_events.csv", io.BytesIO(file_bytes), "text/csv")},
    )
    assert res_commit.status_code == 200
    cdata = res_commit.json()
    assert cdata["status"] == "committed"
    assert cdata["saved_count"] >= 4

    logs = get_audit_logs(limit=5)
    assert any("timeline_events" in l["what"].lower() for l in logs)


def test_b1_edit_fee_reduction_and_student_assistant_reflection(admin_headers, student_auth):
    sid = student_auth["student_id"]
    s_headers = student_auth["headers"]

    # Student chooses scholarship
    sch_name = "Merit Scholarship - Undergraduate"
    client.post("/api/scholarship/choose", headers=s_headers, json={"scholarship": sch_name})

    # Admin fetches scholarship_facts
    res_facts = client.get("/api/admin/crud/scholarship_facts", headers=admin_headers)
    assert res_facts.status_code == 200
    facts = res_facts.json()
    fee_fact = next(f for f in facts if f["scholarship_id"] == sch_name and "Fee Reduction" in f["label"])
    fact_id = fee_fact["id"]

    # Admin updates fee reduction to 95% Tuition Fee Waiver
    new_value = "95% Tuition Fee Waiver (Special B1 Award)"
    res_put = client.put(
        f"/api/admin/crud/scholarship_facts/{fact_id}",
        headers=admin_headers,
        json={"value": new_value},
    )
    assert res_put.status_code == 200

    # Verify audit log recorded this edit
    logs = get_audit_logs(limit=5)
    assert any(f"ID {fact_id}" in l["what"] or "scholarship_facts" in l["what"].lower() for l in logs)

    # Student state immediately reflects new fact
    res_state = client.get("/api/state", headers=s_headers)
    assert res_state.status_code == 200
    state_data = res_state.json()
    updated_state_fact = next(f for f in state_data["facts"] if f["id"] == fact_id)
    assert updated_state_fact["value"] == new_value

    # Assistant answers questions about fee reduction using database facts
    res_chat = answer(sid, "how much fee reduction do I get?", chosen=sch_name)
    assert "95%" in res_chat["answer"]
    assert "scholarship_facts" in res_chat["sources"]


def test_b1_admin_deadline_banner_update(admin_headers, student_auth):
    s_headers = student_auth["headers"]
    banner_text = "Special Alert: Extended Deadline until October 15, 2026!"

    res = client.post(
        "/api/admin/settings/deadline-banner",
        headers=admin_headers,
        json={"text": banner_text},
    )
    assert res.status_code == 200

    # Student state receives updated banner
    res_state = client.get("/api/state", headers=s_headers)
    assert res_state.status_code == 200
    assert res_state.json()["deadline_banner"] == banner_text
