"""Service for admin data management, CRUD, bulk import/export, and audit logging."""
import io
import csv
from typing import Optional, Any
from sqlmodel import select
from openpyxl import load_workbook

from src.database.db import get_session, add_audit_log, conn
from src.database.models import (
    Scholarship,
    ScholarshipFact,
    RequiredDocument,
    TimelineEvent,
    Office,
    Announcement,
    Setting,
    AuditLog,
)

TABLE_MODELS = {
    "scholarships": Scholarship,
    "scholarship_facts": ScholarshipFact,
    "required_documents": RequiredDocument,
    "timeline_events": TimelineEvent,
    "offices": Office,
    "announcements": Announcement,
}

COLUMN_ALIASES = {
    "scholarships": {
        "scholarship": "name",
        "scholarship_name": "name",
        "title": "name",
    },
    "scholarship_facts": {
        "scholarship": "scholarship_id",
        "scholarship_name": "scholarship_id",
        "order": "sort_order",
    },
    "required_documents": {
        "scholarship": "scholarship_name",
        "document": "doc_type",
        "document_type": "doc_type",
        "type": "doc_type",
    },
    "timeline_events": {
        "key": "event_key",
        "event": "event_key",
        "date": "date_str",
        "order": "order_num",
    },
    "offices": {
        "dept": "category",
        "department": "category",
        "office_name": "name",
        "keywords": "routing_keywords",
    },
    "announcements": {
        "message": "body",
        "content": "body",
        "is_active": "active",
    },
}

REQUIRED_FIELDS = {
    "scholarships": ["name"],
    "scholarship_facts": ["scholarship_id", "label", "value"],
    "required_documents": ["scholarship_name", "doc_type"],
    "timeline_events": ["event_key", "title", "date_str"],
    "offices": ["category", "name"],
    "announcements": ["title", "body"],
}


def parse_import_file(content: bytes, filename: str) -> list[dict]:
    """Parse CSV or XLSX binary content into a list of row dictionaries."""
    fn_lower = filename.lower()
    rows: list[dict] = []
    if fn_lower.endswith(".xlsx"):
        wb = load_workbook(filename=io.BytesIO(content), data_only=True)
        sheet = wb.active
        headers = []
        for i, row in enumerate(sheet.iter_rows(values_only=True)):
            if i == 0:
                headers = [str(cell).strip() if cell is not None else f"col_{c}" for c, cell in enumerate(row)]
                continue
            if not any(row):
                continue
            row_dict = {}
            for col_idx, cell_value in enumerate(row):
                if col_idx < len(headers):
                    val = "" if cell_value is None else str(cell_value).strip()
                    row_dict[headers[col_idx]] = val
            rows.append(row_dict)
    else:
        # Default to CSV
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            cleaned = {str(k).strip(): (str(v).strip() if v is not None else "") for k, v in row.items() if k}
            if any(cleaned.values()):
                rows.append(cleaned)
    return rows


def normalize_row_keys(table: str, row: dict) -> dict:
    """Normalize row column names based on table aliases and standard columns."""
    aliases = COLUMN_ALIASES.get(table, {})
    norm: dict = {}
    for k, v in row.items():
        clean_k = k.lower().replace(" ", "_").strip()
        final_k = aliases.get(clean_k, clean_k)
        norm[final_k] = v
    return norm


def validate_and_preview(table: str, raw_rows: list[dict]) -> dict:
    """Validate rows against table rules, return valid rows and error reports."""
    if table not in TABLE_MODELS:
        raise ValueError(f"Unknown table: '{table}'. Allowed: {list(TABLE_MODELS.keys())}")

    req_fields = REQUIRED_FIELDS.get(table, [])
    valid_rows = []
    errors = []

    for idx, raw in enumerate(raw_rows, start=1):
        row = normalize_row_keys(table, raw)
        missing = [rf for rf in req_fields if not row.get(rf)]
        if missing:
            errors.append({
                "row_number": idx,
                "data": raw,
                "error": f"Missing required field(s): {', '.join(missing)}"
            })
            continue

        # Type casts / cleanups
        cleaned: dict[str, Any] = dict(row)
        if table == "scholarships":
            try:
                cleaned["year"] = int(row.get("year", 2026)) if row.get("year") else 2026
            except ValueError:
                cleaned["year"] = 2026
            try:
                cleaned["version"] = int(row.get("version", 1)) if row.get("version") else 1
            except ValueError:
                cleaned["version"] = 1
        elif table == "scholarship_facts":
            try:
                cleaned["sort_order"] = int(row.get("sort_order", 0)) if row.get("sort_order") else 0
            except ValueError:
                cleaned["sort_order"] = 0
        elif table == "timeline_events":
            try:
                cleaned["order_num"] = int(row.get("order_num", 0)) if row.get("order_num") else 0
            except ValueError:
                cleaned["order_num"] = 0
        elif table == "announcements":
            try:
                cleaned["active"] = int(row.get("active", 1)) if str(row.get("active", "")).strip() != "" else 1
            except ValueError:
                cleaned["active"] = 1

        valid_rows.append(cleaned)

    return {
        "table": table,
        "total_rows": len(raw_rows),
        "valid_count": len(valid_rows),
        "error_count": len(errors),
        "errors": errors,
        "preview_sample": valid_rows[:10],
        "valid_rows": valid_rows,
    }


def commit_import_rows(table: str, valid_rows: list[dict], who: str = "admin") -> int:
    """Upsert valid rows into table and log to audit_log."""
    if table not in TABLE_MODELS:
        raise ValueError(f"Unknown table '{table}'")

    model_cls = TABLE_MODELS[table]
    count = 0

    with get_session() as session:
        for row in valid_rows:
            if table == "scholarships":
                existing = session.exec(select(Scholarship).where(Scholarship.name == row["name"])).first()
                if existing:
                    existing.description = row.get("description", existing.description)
                    existing.year = row.get("year", existing.year)
                    existing.version = row.get("version", existing.version)
                else:
                    session.add(Scholarship(**row))
            elif table == "scholarship_facts":
                existing = session.exec(
                    select(ScholarshipFact).where(
                        ScholarshipFact.scholarship_id == row["scholarship_id"],
                        ScholarshipFact.label == row["label"],
                    )
                ).first()
                if existing:
                    existing.value = row["value"]
                    existing.sort_order = row.get("sort_order", existing.sort_order)
                else:
                    session.add(ScholarshipFact(**row))
            elif table == "required_documents":
                existing = session.exec(
                    select(RequiredDocument).where(
                        RequiredDocument.scholarship_name == row["scholarship_name"],
                        RequiredDocument.doc_type == row["doc_type"],
                    )
                ).first()
                if existing:
                    existing.description = row.get("description", existing.description)
                else:
                    session.add(RequiredDocument(**row))
            elif table == "timeline_events":
                existing = session.exec(
                    select(TimelineEvent).where(TimelineEvent.event_key == row["event_key"])
                ).first()
                if existing:
                    existing.title = row["title"]
                    existing.date_str = row["date_str"]
                    existing.order_num = row.get("order_num", existing.order_num)
                else:
                    session.add(TimelineEvent(**row))
            elif table == "offices":
                existing = session.exec(
                    select(Office).where(Office.category == row["category"])
                ).first()
                if existing:
                    existing.name = row["name"]
                    existing.email = row.get("email", existing.email)
                    existing.phone = row.get("phone", existing.phone)
                    existing.description = row.get("description", existing.description)
                    existing.routing_keywords = row.get("routing_keywords", existing.routing_keywords)
                else:
                    session.add(Office(**row))
            elif table == "announcements":
                session.add(Announcement(**row))
            count += 1

        session.commit()

    add_audit_log(who, f"Bulk imported {count} rows into table '{table}'")
    return count


def list_table_rows(table: str) -> list[dict]:
    """Retrieve all rows for an editable admin table."""
    if table not in TABLE_MODELS:
        raise ValueError(f"Unknown table '{table}'")

    model_cls = TABLE_MODELS[table]
    with get_session() as session:
        stmt = select(model_cls)
        if table == "scholarship_facts":
            stmt = stmt.order_by(ScholarshipFact.scholarship_id, ScholarshipFact.sort_order)
        elif table == "timeline_events":
            stmt = stmt.order_by(TimelineEvent.order_num)
        elif table == "announcements":
            stmt = stmt.order_by(Announcement.id.desc())
        items = session.exec(stmt).all()
        return [item.model_dump() for item in items]


def create_table_row(table: str, data: dict, who: str = "admin") -> dict:
    """Add a row to an admin table and record audit log."""
    if table not in TABLE_MODELS:
        raise ValueError(f"Unknown table '{table}'")

    model_cls = TABLE_MODELS[table]
    with get_session() as session:
        item = model_cls(**data)
        session.add(item)
        session.commit()
        session.refresh(item)
        res = item.model_dump()

    identifier = res.get("name") or res.get("title") or res.get("event_key") or res.get("label") or res.get("id")
    add_audit_log(who, f"Created {table} record '{identifier}'")
    return res


def update_table_row(table: str, row_id: int, data: dict, who: str = "admin") -> dict:
    """Update a row in an admin table and record audit log."""
    if table not in TABLE_MODELS:
        raise ValueError(f"Unknown table '{table}'")

    model_cls = TABLE_MODELS[table]
    with get_session() as session:
        item = session.get(model_cls, row_id)
        if not item:
            raise KeyError(f"{table} item with id {row_id} not found")
        for k, v in data.items():
            if hasattr(item, k) and k != "id":
                setattr(item, k, v)
        session.add(item)
        session.commit()
        session.refresh(item)
        res = item.model_dump()

    identifier = res.get("name") or res.get("title") or res.get("label") or res.get("id")
    add_audit_log(who, f"Updated {table} record ID {row_id} ('{identifier}')")
    return res


def delete_table_row(table: str, row_id: int, who: str = "admin") -> bool:
    """Delete a row from an admin table and record audit log."""
    if table not in TABLE_MODELS:
        raise ValueError(f"Unknown table '{table}'")

    model_cls = TABLE_MODELS[table]
    with get_session() as session:
        item = session.get(model_cls, row_id)
        if not item:
            return False
        identifier = getattr(item, "name", None) or getattr(item, "title", None) or getattr(item, "label", None) or row_id
        session.delete(item)
        session.commit()

    add_audit_log(who, f"Deleted {table} record ID {row_id} ('{identifier}')")
    return True
