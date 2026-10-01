import os
import json
import pytest
from fastapi.testclient import TestClient

from api import app
from src.database.db import get_catalog, get_required_documents
from src.services.kb import (
    extract_document_text_and_chunks,
    create_draft,
    get_draft,
    publish_draft,
    delete_draft,
)
from src.rag.retrieve import retrieve
from src.services.assistant import detect_conflict, answer

client = TestClient(app)

@pytest.fixture(autouse=True)
def restore_master_deadline():
    from src.database.db import conn
    c = conn()
    c.execute("UPDATE timeline_events SET date_str=? WHERE event_key=?", ("Tonight, 11:59 PM", "deadline"))
    c.commit()
    yield
    c = conn()
    c.execute("UPDATE timeline_events SET date_str=? WHERE event_key=?", ("Tonight, 11:59 PM", "deadline"))
    c.commit()

def test_kb_extract_pdf_chunks():
    pdf_path = "data/scholarships/merit_ug_2026_v3.pdf"
    assert os.path.exists(pdf_path)
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    full_text, chunks = extract_document_text_and_chunks(file_bytes, "merit_ug_2026_v3.pdf")
    assert len(full_text) > 0
    assert len(chunks) > 0
    assert all("text" in c and "page" in c for c in chunks)
    assert chunks[0]["page"] >= 1

def test_kb_publish_and_delete_lifecycle():
    # 1. Create a draft for a test scholarship
    test_sch = "Research Excellence Award"
    file_name = "test_research_award_2026.pdf"
    extracted_data = {
        "scholarship_name": test_sch,
        "year": 2026,
        "version": 1,
        "required_documents": ["Research Proposal", "Identity Proof", "Faculty Recommendation"],
        "dates": {"research_deadline": "30 Nov 2026", "research_results": "15 Dec 2026"},
        "offices": [{"name": "Dean of Research", "category": "RESEARCH"}],
    }
    chunks = [
        {"text": "Research Excellence Award provides full tuition grant for undergraduate researchers.", "page": 1},
        {"text": "Research Proposal must be endorsed by a department faculty mentor.", "page": 1},
    ]

    draft = create_draft(file_name, extracted_data, chunks)
    assert draft.id is not None
    assert draft.status == "draft"

    # 2. Publish draft
    pub_res = publish_draft(draft.id)
    assert pub_res["status"] == "published"
    assert pub_res["chunks_indexed"] == 2

    # Verify database updates
    catalog = get_catalog()
    assert test_sch in catalog
    reqs = get_required_documents(test_sch)
    assert "Research Proposal" in reqs
    assert "Faculty Recommendation" in reqs

    # Verify RAG hybrid retrieval finds chunks from newly published document
    current, older, dist = retrieve("research proposal mentor", test_sch)
    assert len(current) > 0
    assert any("Research Proposal must be endorsed" in c["text"] for c in current)

    # 3. Delete draft
    del_res = delete_draft(draft.id)
    assert del_res["status"] == "deleted"

    # Verify Chroma chunks for this document are removed
    current_after, _, _ = retrieve("research proposal mentor", test_sch)
    assert len(current_after) == 0

def test_generic_conflict_detection():
    # Older vs newer version conflict
    older_chunks = [{
        "text": "Income Certificate: a previous-year certificate is accepted if attested.",
        "source": "merit_ug_2025_v1.pdf",
        "year": 2025,
        "version": 1,
    }]
    current_chunks = [{
        "text": "Income Certificate: only a current-year certificate is valid; previous-year certificates are not accepted.",
        "source": "merit_ug_2026_v3.pdf",
        "year": 2026,
        "version": 3,
    }]

    conflict, unresolved = detect_conflict("income certificate validity", current_chunks, older_chunks)
    assert unresolved is False
    assert conflict is not None
    assert conflict["older_year"] == 2025
    assert conflict["current_year"] == 2026
    assert "previous-year certificate is accepted" in conflict["older_rule"]

    # Same year and version disagreement -> marked UNRESOLVED
    conflicting_same_version = [
        {
            "text": "Income Certificate: previous-year certificate is accepted.",
            "source": "guideline_a.pdf",
            "year": 2026,
            "version": 1,
        },
        {
            "text": "Income Certificate: previous-year certificate is not accepted.",
            "source": "guideline_b.pdf",
            "year": 2026,
            "version": 1,
        }
    ]
    conflict_sv, unresolved_sv = detect_conflict("income certificate", conflicting_same_version, [])
    assert unresolved_sv is True
    assert conflict_sv is None

def test_kb_api_routes(monkeypatch):
    import src.services.kb as kb_service
    from src.services.auth import create_admin_session
    admin_token = create_admin_session()
    headers = {"Authorization": f"Bearer {admin_token}"}

    monkeypatch.setattr(kb_service, "ask_llm", lambda sys, usr: json.dumps({
        "scholarship_name": "API Test Scholarship",
        "year": 2026,
        "version": 1,
        "required_documents": ["Marksheet"],
        "dates": {"api_deadline": "Tomorrow"},
        "offices": [],
    }))

    # Test admin html page served
    resp = client.get("/admin")
    assert resp.status_code == 200
    assert "Knowledge Base" in resp.text

    # Test list drafts
    drafts_resp = client.get("/admin/kb/drafts", headers=headers)
    assert drafts_resp.status_code == 200
    assert isinstance(drafts_resp.json(), list)

    # Test upload endpoint with synthetic PDF content
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n>>\n%%EOF"
    upload_resp = client.post(
        "/admin/kb/upload",
        files={"file": ("test_policy.pdf", pdf_content, "application/pdf")},
        headers=headers,
    )
    assert upload_resp.status_code == 200
    data = upload_resp.json()
    assert "id" in data
    assert data["status"] == "draft"
    draft_id = data["id"]

    # Test get draft by id
    get_resp = client.get(f"/admin/kb/{draft_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == draft_id

    # Test publish draft
    publish_resp = client.post(
        f"/admin/kb/{draft_id}/publish",
        json={
            "scholarship_name": "API Test Scholarship",
            "year": 2026,
            "version": 1,
            "required_documents": ["Marksheet"],
            "dates": {"api_deadline": "Tomorrow"},
            "offices": [],
        },
        headers=headers,
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["status"] == "published"

    # Test delete draft
    del_resp = client.delete(f"/admin/kb/{draft_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"
