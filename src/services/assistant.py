import json
import os
from datetime import datetime, timezone
from src.database.db import conn, get_catalog, get_timeline
from src.rag.retrieve import retrieve
from src.services.checklist import checklist
from src.services.llm import ask_llm
from src.services.routing import classify, OFFICE

class _CatalogProxy(list):
    """Dynamic proxy for scholarships catalog queried from database."""
    def __iter__(self):
        return iter(get_catalog())
    def __len__(self):
        return len(get_catalog())
    def __contains__(self, item):
        return item in get_catalog()
    def __getitem__(self, index):
        return get_catalog()[index]

CATALOG = _CatalogProxy()

class _TimelineProxy(dict):
    """Dynamic proxy for timeline dates queried from database."""
    def __getitem__(self, key):
        return get_timeline().get(key, "")
    def get(self, key, default=None):
        return get_timeline().get(key, default)
    def items(self):
        return get_timeline().items()
    def __iter__(self):
        return iter(get_timeline())

T = _TimelineProxy()
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

def get_recent_history(student_id: str, limit: int = 6) -> list[dict]:
    """Retrieve last N turns (user/assistant) from chat_messages table."""
    try:
        with conn() as c:
            rows = c.execute(
                "SELECT role, content FROM chat_messages WHERE student_id=? ORDER BY id DESC LIMIT ?",
                (student_id, limit * 2)
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception:
        return []

def record_chat_message(student_id: str, role: str, content: str, session_id: str = None):
    """Store every chat message in chat_messages table."""
    try:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        sid = session_id or f"sess_{student_id}"
        with conn() as c:
            c.execute(
                "INSERT INTO chat_messages (session_id, student_id, role, content, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (sid, student_id, role, content, "{}", now_str)
            )
            c.commit()
    except Exception:
        pass

def reply(answer, status, sources=None, items=None, options=None, next_action="", conflict=None, steps=None, office="", label=""):
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
        "label": label,
    }

def detect_conflict(query, current, older, scholarship=None):
    """Generic conflict check:
    1. Same year and version disagreeing on a requirement -> marked UNRESOLVED and routed to office.
    2. Same scholarship and requirement key between versions -> newest published version wins, older shown as a conflict card.
    """
    if not current and not older:
        return None, False

    # Check for same year/version contradiction on the same requirement
    opposing_pairs = [
        ("not accepted", "accepted"),
        ("previous-year", "current-year"),
        ("mandatory", "optional"),
        ("exempt", "required"),
    ]
    if len(current) >= 2:
        for i in range(len(current)):
            for j in range(i + 1, len(current)):
                c1, c2 = current[i], current[j]
                if c1.get("year") == c2.get("year") and c1.get("version") == c2.get("version"):
                    t1, t2 = c1["text"].lower(), c2["text"].lower()
                    for pos, neg in opposing_pairs:
                        if (pos in t1 and neg in t2 and pos not in t2) or (pos in t2 and neg in t1 and pos not in t1):
                            return None, True

    if not older:
        return None, False

    # Generic version conflict check (older vs current)
    from src.services.checklist import REQS
    doc_keys = [k.lower() for k in REQS.get(scholarship or "", [])]
    generic_keys = ["income", "identity", "marksheet", "bank", "category", "caste", "certificate", "fee", "deadline", "verification"]
    all_keys = list(dict.fromkeys(doc_keys + generic_keys))

    text_corpus = (query + " " + " ".join(h["text"] for h in current)).lower()

    matched_key = None
    for k in all_keys:
        if k in text_corpus and any(k in h["text"].lower() for h in older):
            matched_key = k
            break

    if matched_key:
        older_chunk = next((h for h in older if matched_key in h["text"].lower()), older[0])
        current_chunk = next((h for h in current if matched_key in h["text"].lower()), current[0])
        if older_chunk["text"] != current_chunk["text"]:
            return {
                "older_rule": older_chunk["text"],
                "older_source": older_chunk.get("source", ""),
                "older_year": older_chunk.get("year", 2025),
                "current_rule": current_chunk["text"],
                "current_source": current_chunk.get("source", ""),
                "current_year": current_chunk.get("year", 2026),
            }, False

    return None, False

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

def answer(student_id, message, chosen=None, lang_override=None, session_id=None):
    # 1. Record incoming user message in chat_messages table
    record_chat_message(student_id, "user", message, session_id=session_id)
    history = get_recent_history(student_id, limit=6)

    s = get_student(student_id)
    language = lang_override or s.get("language") or "English"
    cat = classify(message)
    scholarship = chosen or s.get("scholarship", "")

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
        res = reply(msg_text, "escalated", next_action=f"Contact {office}", office=office)
        record_chat_message(student_id, "assistant", res["answer"], session_id=session_id)
        return res

    if not scholarship:                                 # ambiguous: ask before answering
        res = reply("I found multiple scholarships matching your profile. Which one are you applying for?",
                     "clarify", options=CATALOG)
        record_chat_message(student_id, "assistant", res["answer"], session_id=session_id)
        return res

    current, older, best_dist = retrieve(message, scholarship)
    if not current or best_dist > SCOPE_THRESHOLD:
        office = "Financial Aid / Scholarship Office"
        log(student_id, "OUT_OF_SCOPE", message, 0, office)
        history_context = "\n".join(f"{h['role'].title()}: {h['content']}" for h in history[-6:])
        general_prompt = f"""Recent conversation turns:
{history_context}

User question: {message}

Please provide a helpful, concise answer (max 3 sentences) in {language}. Note that this is not covered by official scholarship policies."""
        try:
            gen_ans = ask_llm("You are a helpful university AI assistant. Provide a concise answer to the student's question.", general_prompt).strip()
        except Exception:
            gen_ans = "This topic is outside the official scholarship documents."

        combined_text = (
            f"[General answer, not from scholarship documents]\n"
            f"{gen_ans}\n\n"
            f"Note: this question is outside the scholarship rules.\n\n"
            f"What to do next: please contact the {office}."
        )
        res = reply(combined_text, "out_of_scope", next_action=f"Contact {office}", office=office, label="General answer, not from scholarship documents")
        record_chat_message(student_id, "assistant", res["answer"], session_id=session_id)
        return res

    items = checklist(student_id, scholarship)
    problems = [i for i in items if i[1] != "OK"]
    conflict, unresolved = detect_conflict(message, current, older, scholarship=scholarship)
    if unresolved:
        office = "Financial Aid / Scholarship Office"
        log(student_id, "POLICY_CONFLICT", message, 0, office)
        res = reply(
            "There is an unresolved contradiction in the scholarship guidelines for this academic session. This issue has been marked UNRESOLVED and escalated to the scholarship office.\n\nWhat to do next: contact the Financial Aid / Scholarship Office.",
            "escalated",
            office=office,
            next_action=f"Contact {office}"
        )
        record_chat_message(student_id, "assistant", res["answer"], session_id=session_id)
        return res

    steps = build_steps(problems, T["deadline"], message)

    timeline_str = ", ".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in T.items())
    history_str = "\n".join(f"{h['role'].title()}: {h['content']}" for h in history[-6:])
    context = (f"STUDENT: {s['name']}, {s['branch']}\n"
               f"LANGUAGE: {language}\n"
               f"SCHOLARSHIP: {scholarship}\n"
               f"TIMELINE: {timeline_str}\n"
               f"RECENT CONVERSATION:\n{history_str}\n"
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
    res = reply(text, status, sources=sources, items=items, conflict=conflict, steps=steps)
    record_chat_message(student_id, "assistant", res["answer"], session_id=session_id)
    return res
