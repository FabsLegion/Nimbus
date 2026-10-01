"""Knowledge base document ingestion, metadata extraction, and draft management."""
import io
import json
import re
from typing import Optional
from pydantic import BaseModel, Field
import fitz
import pymupdf4llm
from sqlmodel import select

from src.database.db import get_session
from src.database.models import (
    KnowledgeDraft,
    Scholarship,
    RequiredDocument,
    TimelineEvent,
    Office,
)
from src.rag.ingest import add_document_chunks, delete_source_chunks
from src.services.llm import ask_llm

class KBDraftExtraction(BaseModel):
    scholarship_name: str = Field(description="Full name of scholarship program or policy document title")
    kind: str = Field(default="scholarship", description="Document type: scholarship, fee, hostel, calendar, faq, or notice")
    year: int = Field(default=2026, description="Academic year")
    version: int = Field(default=1, description="Version number of policy")
    required_documents: list[str] = Field(default_factory=list, description="List of required certificates/documents")
    dates: dict[str, str] = Field(default_factory=dict, description="Key timeline dates like deadline, verification, results")
    offices: list[dict[str, str]] = Field(default_factory=list, description="Offices mentioned and their categories")

def extract_document_text_and_chunks(file_bytes: bytes, filename: str) -> tuple[str, list[dict]]:
    """Extract full markdown text and page-attributed chunks from document bytes."""
    ext = filename.lower().split(".")[-1]
    chunks: list[dict] = []
    full_text_parts: list[str] = []

    if ext == "pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            # Use PyMuPDF4LLM for clean markdown with page chunks
            page_data = pymupdf4llm.to_markdown(doc, page_chunks=True)
            for item in page_data:
                p_num = item.get("metadata", {}).get("page", 1)
                p_text = item.get("text", "").strip()
                if not p_text:
                    continue
                full_text_parts.append(p_text)
                for line in p_text.split("\n"):
                    cleaned = line.strip()
                    if cleaned and not cleaned.startswith("#") and len(cleaned) > 5:
                        chunks.append({"text": cleaned, "page": p_num})
        except Exception:
            # Fallback to standard PyMuPDF
            for idx, page in enumerate(doc, start=1):
                p_text = page.get_text().strip()
                if p_text:
                    full_text_parts.append(p_text)
                    for line in p_text.split("\n"):
                        cleaned = line.strip()
                        if cleaned:
                            chunks.append({"text": cleaned, "page": idx})
    else:
        # Plain text / docx text fallback
        text = file_bytes.decode("utf-8", errors="ignore")
        full_text_parts.append(text)
        for line in text.split("\n"):
            cleaned = line.strip()
            if cleaned:
                chunks.append({"text": cleaned, "page": 1})

    return "\n\n".join(full_text_parts), chunks

def _clean_json_response(raw_text: str) -> str:
    """Extract valid JSON from potential markdown code fences."""
    cleaned = raw_text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        return match.group(1)
    # Match outermost braces
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        return cleaned[start : end + 1]
    return cleaned

def _detect_kind(text: str, filename: str = "") -> str:
    comb = f"{filename} {text[:1000]}".lower()
    if any(k in comb for k in ["fee", "tuition", "payment policy"]):
        return "fee"
    if any(k in comb for k in ["hostel", "mess", "curfew", "warden", "room allocation"]):
        return "hostel"
    if any(k in comb for k in ["calendar", "academic calendar", "semester start", "re-opening"]):
        return "calendar"
    if any(k in comb for k in ["faq", "frequently asked"]):
        return "faq"
    if any(k in comb for k in ["notice", "circular", "announcement"]):
        return "notice"
    return "scholarship"

def extract_draft_metadata(full_text: str) -> dict:
    """Call LLM in JSON mode to extract structured draft metadata with one retry."""
    system = "You are a specialized university document extraction system. Classify the document kind (scholarship, fee, hostel, calendar, faq, notice) and output strictly valid JSON adhering to the required schema."
    prompt = f"""Extract structured metadata and classify the document from the text below:

DOCUMENT TEXT:
\"\"\"
{full_text[:4000]}
\"\"\"

Return a JSON object with this exact structure:
{{
  "scholarship_name": "Full Document Title or Scholarship Name",
  "kind": "scholarship",
  "year": 2026,
  "version": 1,
  "required_documents": ["Identity Proof", "Income Certificate", ...],
  "dates": {{"deadline": "...", "verification": "...", "results": "..."}},
  "offices": [{{"name": "...", "category": "..."}}]
}}
Valid values for "kind": "scholarship", "fee", "hostel", "calendar", "faq", "notice".
"""
    # Attempt 1
    for attempt in range(2):
        try:
            resp = ask_llm(system, prompt if attempt == 0 else prompt + "\nNOTE: Return strictly valid JSON with double-quoted keys.")
            json_str = _clean_json_response(resp)
            validated = KBDraftExtraction.model_validate_json(json_str)
            res = validated.model_dump()
            if not res.get("kind") or res["kind"] not in ["scholarship", "fee", "hostel", "calendar", "faq", "notice"]:
                res["kind"] = _detect_kind(full_text)
            return res
        except Exception as e:
            if attempt == 1:
                # Fallback extraction from first line header if available
                first_line = full_text.split("\n")[0] if full_text else ""
                name, yr, ver = "New Document", 2026, 1
                if "|" in first_line:
                    parts = [p.strip() for p in first_line.split("|")]
                    if len(parts) >= 3:
                        name = parts[0]
                        try: yr = int(parts[1])
                        except: pass
                        try: ver = int(parts[2].lstrip("v"))
                        except: pass
                kind = _detect_kind(f"{name} {full_text}")
                return {
                    "scholarship_name": name,
                    "kind": kind,
                    "year": yr,
                    "version": ver,
                    "required_documents": ["Identity Proof", "Marksheet"] if kind == "scholarship" else [],
                    "dates": {"deadline": "Tonight, 11:59 PM"} if kind == "scholarship" else {},
                    "offices": [],
                }

def create_draft(file_name: str, extracted: dict, chunks: list[dict]) -> KnowledgeDraft:
    """Save extracted draft into knowledge_drafts table."""
    kind = extracted.get("kind")
    if not kind or kind not in ["scholarship", "fee", "hostel", "calendar", "faq", "notice"]:
        kind = _detect_kind(extracted.get("scholarship_name", ""), file_name)

    with get_session() as session:
        draft = KnowledgeDraft(
            file_name=file_name,
            scholarship_name=extracted.get("scholarship_name", "Untitled Document"),
            kind=kind,
            year=int(extracted.get("year", 2026)),
            version=int(extracted.get("version", 1)),
            required_documents_json=json.dumps(extracted.get("required_documents", [])),
            dates_json=json.dumps(extracted.get("dates", {})),
            offices_json=json.dumps(extracted.get("offices", [])),
            chunks_json=json.dumps(chunks),
            status="draft",
        )
        session.add(draft)
        session.commit()
        session.refresh(draft)
        return draft

def get_draft(draft_id: int) -> Optional[KnowledgeDraft]:
    """Retrieve draft by ID."""
    with get_session() as session:
        return session.get(KnowledgeDraft, draft_id)

def list_drafts() -> list[KnowledgeDraft]:
    """Return all knowledge drafts."""
    with get_session() as session:
        return list(session.exec(select(KnowledgeDraft).order_by(KnowledgeDraft.id.desc())).all())

def publish_draft(draft_id: int, updates: Optional[dict] = None) -> dict:
    """Publish draft: write structured rows to SQLite and add chunks to Chroma."""
    with get_session() as session:
        draft = session.get(KnowledgeDraft, draft_id)
        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        # Merge updates if provided by admin
        if updates:
            draft.scholarship_name = updates.get("scholarship_name", draft.scholarship_name)
            if "kind" in updates and updates["kind"]:
                draft.kind = updates["kind"]
            draft.year = int(updates.get("year", draft.year))
            draft.version = int(updates.get("version", draft.version))
            if "required_documents" in updates:
                draft.required_documents_json = json.dumps(updates["required_documents"])
            if "dates" in updates:
                draft.dates_json = json.dumps(updates["dates"])
            if "offices" in updates:
                draft.offices_json = json.dumps(updates["offices"])

        sch_name = draft.scholarship_name
        req_docs = json.loads(draft.required_documents_json)
        dates = json.loads(draft.dates_json)
        offices = json.loads(draft.offices_json)
        chunks = json.loads(draft.chunks_json)

        # Only kind=scholarship creates rows in scholarships and required_documents.
        # The other kinds are only indexed for the assistant.
        if draft.kind == "scholarship":
            # 1. Update/insert Scholarship
            sch = session.exec(select(Scholarship).where(Scholarship.name == sch_name)).first()
            if not sch:
                sch = Scholarship(name=sch_name, year=draft.year, version=draft.version)
                session.add(sch)
            else:
                sch.year = draft.year
                sch.version = draft.version

            # 2. Update/insert Required Documents
            for doc in req_docs:
                existing = session.exec(select(RequiredDocument).where(
                    RequiredDocument.scholarship_name == sch_name,
                    RequiredDocument.doc_type == doc
                )).first()
                if not existing:
                    session.add(RequiredDocument(scholarship_name=sch_name, doc_type=doc))

        # 3. Update timeline events
        for k, v in dates.items():
            ev = session.exec(select(TimelineEvent).where(TimelineEvent.event_key == k)).first()
            if ev:
                ev.date_str = str(v)
            else:
                session.add(TimelineEvent(event_key=k, title=k.replace('_', ' ').title(), date_str=str(v)))

        # 4. Update offices if provided
        for off in offices:
            if isinstance(off, dict) and "name" in off and "category" in off:
                existing_off = session.exec(select(Office).where(Office.category == off["category"])).first()
                if not existing_off:
                    session.add(Office(category=off["category"], name=off["name"]))

        draft.status = "published"
        session.commit()

        # 5. Add only this document's chunks to ChromaDB
        indexed_count = add_document_chunks(
            source_filename=draft.file_name,
            scholarship=sch_name,
            year=draft.year,
            version=draft.version,
            chunks=chunks
        )

        return {
            "id": draft.id,
            "status": "published",
            "scholarship_name": sch_name,
            "chunks_indexed": indexed_count
        }

def delete_draft(draft_id: int) -> dict:
    """Delete draft and remove only its chunks from ChromaDB."""
    with get_session() as session:
        draft = session.get(KnowledgeDraft, draft_id)
        if not draft:
            return {"status": "not_found"}

        file_name = draft.file_name
        sch_name = draft.scholarship_name

        # Delete only its chunks from Chroma
        delete_source_chunks(file_name)

        # Clean up scholarship and required docs if no other draft or student uses this scholarship
        other_drafts = session.exec(select(KnowledgeDraft).where(
            KnowledgeDraft.scholarship_name == sch_name,
            KnowledgeDraft.id != draft.id
        )).first()
        from src.database.models import Student
        student_using = session.exec(select(Student).where(Student.scholarship == sch_name)).first()
        if not other_drafts and not student_using:
            sch = session.exec(select(Scholarship).where(Scholarship.name == sch_name)).first()
            if sch:
                session.delete(sch)
            req_docs = session.exec(select(RequiredDocument).where(RequiredDocument.scholarship_name == sch_name)).all()
            for rd in req_docs:
                session.delete(rd)

        session.delete(draft)
        session.commit()
        return {"status": "deleted", "file_name": file_name, "scholarship_name": sch_name}
