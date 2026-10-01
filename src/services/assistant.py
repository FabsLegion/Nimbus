import json
import os
from src.database.db import conn
from src.rag.retrieve import retrieve
from src.services.checklist import checklist
from src.services.llm import ask_llm
from src.services.routing import classify, OFFICE

CATALOG = ["Merit Scholarship - Undergraduate", "Merit Scholarship - Special Category"]
T = json.load(open("data/master_timeline.json"))
SCOPE_THRESHOLD = float(os.getenv("SCOPE_THRESHOLD", "30.0"))

SYSTEM = """You are a helpful university scholarship guidance assistant.
Max 3 sentences. No file names. No step list. The interface shows steps, sources and the conflict.
Explain clearly and concisely in the requested language. Use only the provided facts."""

def get_student(sid):
    return dict(conn().execute("SELECT * FROM students WHERE student_id=?", (sid,)).fetchone())

def log(sid, cat, text, resolved, office=""):
    c = conn()
    c.execute("INSERT INTO queries(student_id,category,text,resolved,office) VALUES (?,?,?,?,?)",
              (sid, cat, text, resolved, office))
    c.commit()

def notify(sid, priority, msg):
    c = conn()
    if not c.execute("SELECT 1 FROM notifications WHERE student_id=? AND message=?", (sid, msg)).fetchone():
        c.execute("INSERT INTO notifications(student_id,priority,message) VALUES (?,?,?)", (sid, priority, msg))
        c.commit()

def reply(answer, status, sources=None, items=None, options=None, next_action="", conflict=None, steps=None, office=""):
    return {
        "answer": answer,
        "status": status,
        "sources": sources or [],
        "checklist": items or [],
        "options": options or [],
        "next_action": next_action,
        "conflict": conflict,
        "steps": steps or [],
        "office": office,
    }

def detect_conflict(query, current, older):
    """Detect if there is an active rule conflict relevant to the query/chunks."""
    if not older:
        return None
    # Check if this query or current chunks touch income certificate conflict
    text_corpus = (query + " " + " ".join(h["text"] for h in current)).lower()
    if any(k in text_corpus for k in ["income", "certificate", "document", "previous", "current-year", "valid"]):
        older_text = next((h["text"] for h in older if "income" in h["text"].lower()), older[0]["text"])
        current_text = next((h["text"] for h in current if "income" in h["text"].lower()), current[0]["text"])
        return {
            "older_rule": older_text,
            "older_source": older[0]["source"],
            "older_year": older[0]["year"],
            "current_rule": current_text,
            "current_source": current[0]["source"],
            "current_year": current[0]["year"],
        }
    return None

def build_steps(problems, deadline, query=""):
    """Deterministically construct What to do next numbered steps."""
    q_lower = query.lower()
    if any(w in q_lower for w in ["after submit", "what happens after", "once submitted", "after i submit"]):
        return [
            f"Verification phase: {T.get('verification', 'Document scrutiny')}.",
            f"Results announcement: {T.get('results', 'Merit list published')}.",
            f"Allotment & disbursement: {T.get('allotment', 'Scholarship credited')}.",
        ]
    steps = []
    for name, st, why in problems:
        if st == "MISSING":
            steps.append(f"Upload your missing {name}.")
        elif st == "INVALID":
            steps.append(f"Replace your {name}: {why}.")
        elif st == "WRONG_CATEGORY":
            steps.append(f"Fix category mismatch for {name}: {why}.")
    if not problems:
        steps.append("Review all uploaded documents.")
        steps.append(f"Submit your finalized application before {deadline}.")
    else:
        steps.append(f"Submit your application before the deadline: {deadline}.")
    return steps

def answer(student_id, message, chosen=None, lang_override=None):
    s = get_student(student_id)
    language = lang_override or s.get("language") or "English"
    cat = classify(message)
    scholarship = chosen or s["scholarship"]

    if cat in OFFICE:                                   # not answerable from scholarship rules
        office = OFFICE[cat]
        log(student_id, cat, message, 0, office)
        msg_text = (f"This looks like a {cat.lower()} issue, which is handled directly by the {office}.\n\n"
                    f"What to do next: contact the {office}.")
        if language.lower() != "english":
            try:
                msg_text = ask_llm(
                    f"Translate the following university guidance message into {language}. Keep the office name '{office}' readable.",
                    msg_text
                )
            except Exception:
                pass
        return reply(msg_text, "escalated", next_action=f"Contact {office}", office=office)

    if not scholarship:                                 # ambiguous: ask before answering
        return reply("I found multiple scholarships matching your profile. Which one are you applying for?",
                     "clarify", options=CATALOG)

    current, older, best_dist = retrieve(message, scholarship)
    if not current or best_dist > SCOPE_THRESHOLD:
        office = "Financial Aid / Scholarship Office"
        log(student_id, "OUT_OF_SCOPE", message, 0, office)
        return reply(f"This question is outside the scholarship rules.\n\n"
                     f"What to do next: please contact the {office}.",
                     "out_of_scope", next_action=f"Contact {office}", office=office)

    items = checklist(student_id, scholarship)
    problems = [i for i in items if i[1] != "OK"]
    conflict = detect_conflict(message, current, older)
    steps = build_steps(problems, T["deadline"], message)

    timeline_str = ", ".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in T.items())
    context = (f"STUDENT: {s['name']}, {s['branch']}\n"
               f"LANGUAGE: {language}\n"
               f"SCHOLARSHIP: {scholarship}\n"
               f"TIMELINE: {timeline_str}\n"
               f"CURRENT RULES: {[h['text'] for h in current]}\n"
               f"SUPERSEDED RULES: {[h['text'] for h in older] if older else 'None'}\n"
               f"CHECKLIST STATUS: {items}\n"
               f"QUESTION: {message}\n"
               f"Remember: Max 3 plain sentences in {language}. No file names. No step list.")

    try:
        text = ask_llm(SYSTEM, context).strip()
    except Exception:
        text = f"Here is the guidance for your {scholarship}. Please review your checklist status and submit all documents before {T['deadline']}."

    if problems:
        notify(student_id, "URGENT", f"{problems[0][0]} needs attention. Deadline: {T['deadline']}")
    log(student_id, cat, message, 1)

    sources = list({h["source"] for h in current + older})
    status = "action_required" if problems else "all_clear"
    return reply(text, status, sources=sources, items=items, conflict=conflict, steps=steps)
