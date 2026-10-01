"""Notifications service: manages student notifications with 4 priorities:
URGENT, DEADLINE, ACTION REQUIRED, INFORMATIONAL.
Created deterministically from the checklist and timeline.
"""
from src.database.db import conn, get_timeline
from src.services.checklist import checklist

PRIORITIES = ["URGENT", "DEADLINE", "ACTION REQUIRED", "INFORMATIONAL"]

def notify(student_id: str, priority: str, message: str):
    """Insert or update a notification for a student."""
    prio = priority.upper().strip()
    if prio not in PRIORITIES:
        prio = "INFORMATIONAL"
    with conn() as c:
        existing = c.execute(
            "SELECT id, priority FROM notifications WHERE student_id=? AND message=?",
            (student_id, message)
        ).fetchone()
        if not existing:
            c.execute(
                "INSERT INTO notifications (student_id, priority, message) VALUES (?, ?, ?)",
                (student_id, prio, message)
            )
            c.commit()
        elif existing["priority"] != prio:
            c.execute(
                "UPDATE notifications SET priority=? WHERE id=?",
                (prio, existing["id"])
            )
            c.commit()

def sync_student_notifications(student_id: str):
    """Synchronize notifications for a student based on their active checklist and timeline."""
    with conn() as c:
        student_row = c.execute("SELECT * FROM students WHERE student_id=?", (student_id,)).fetchone()
        if not student_row:
            return
        student = dict(student_row)
        app_row = c.execute("SELECT * FROM applications WHERE student_id=? ORDER BY id DESC LIMIT 1", (student_id,)).fetchone()

    scholarship = student.get("scholarship", "")
    timeline = get_timeline()
    deadline = timeline.get("deadline", "Tonight, 11:59 PM")
    verification = timeline.get("verification", "03 Oct to 07 Oct")
    results = timeline.get("results", "10 Oct")

    # 1. Timeline notifications
    notify(
        student_id,
        "DEADLINE",
        f"Application submission deadline: {deadline}. Ensure all required documents are uploaded before the cutoff."
    )
    notify(
        student_id,
        "INFORMATIONAL",
        f"Document verification window is scheduled for {verification}."
    )
    notify(
        student_id,
        "INFORMATIONAL",
        f"Official scholarship merit list and results will be declared on {results}."
    )

    # 2. Checklist-based notifications
    if scholarship:
        items = checklist(student_id, scholarship)
        problems = [i for i in items if i[1] != "OK"]
        for name, status, why in problems:
            if status == "INVALID":
                notify(
                    student_id,
                    "URGENT",
                    f"Action Required: Your {name} was rejected ({why or 'verification failed'}). Please re-upload immediately."
                )
            elif status == "WRONG_CATEGORY":
                notify(
                    student_id,
                    "ACTION REQUIRED",
                    f"Category mismatch on {name}: {why}. Please re-upload under the appropriate category."
                )
            elif status == "MISSING":
                notify(
                    student_id,
                    "ACTION REQUIRED",
                    f"Missing document: {name} is required for {scholarship}. Upload before {deadline}."
                )

        if not problems:
            if app_row and app_row["status"] == "submitted":
                notify(
                    student_id,
                    "INFORMATIONAL",
                    f"Application successfully submitted for {scholarship}. Current status: Verification Pending."
                )
            else:
                notify(
                    student_id,
                    "ACTION REQUIRED",
                    f"All documents verified! Please lock and submit your finalized application for {scholarship}."
                )
    else:
        notify(
            student_id,
            "ACTION REQUIRED",
            "Please choose a scholarship program on the Home screen to view your personalized document checklist."
        )
