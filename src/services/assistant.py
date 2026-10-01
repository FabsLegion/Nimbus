import json
from src.database.db import conn
from src.rag.retrieve import retrieve
from src.services.checklist import checklist
from src.services.llm import ask_llm
from src.services.routing import classify, OFFICE

CATALOG = ["Merit Scholarship - Undergraduate", "Merit Scholarship - Special Category"]
T = json.load(open("data/master_timeline.json"))

SYSTEM = """You are a university scholarship guidance assistant.
1. Use only the provided sources and checklist as facts. Never invent requirements, dates or policies.
2. If a CURRENT source and an OLDER source disagree, say there is a conflict and that the CURRENT source applies.
3. Cite the source file name for each factual claim.
4. Personalize the answer using the student's checklist.
5. Explain in simple words, in the student's language.
6. End with "What to do next:" and numbered steps. Mention the deadline.
7. If the information is not in the sources, say so and name the right office."""

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

def reply(answer, status, sources=None, items=None, options=None, next_action=""):
    return {"answer": answer, "status": status, "sources": sources or [], "checklist": items or [],
            "options": options or [], "next_action": next_action}

def answer(student_id, message, chosen=None):
    s = get_student(student_id)
    cat = classify(message)
    scholarship = chosen or s["scholarship"]

    if cat in OFFICE:                                   # not answerable from scholarship rules
        log(student_id, cat, message, 0, OFFICE[cat])
        return reply(f"This looks like a {cat.lower()} issue, which I cannot resolve from the scholarship rules.\n\n"
                     f"What to do next: contact the {OFFICE[cat]}.", "escalated", next_action=OFFICE[cat])

    if not scholarship:                                 # ambiguous: ask before answering
        return reply("I found two scholarships with similar names. Which one are you applying for?",
                     "clarify", options=CATALOG)

    current, older = retrieve(message, scholarship)
    if not current:
        log(student_id, cat, message, 0, "Scholarship Office")
        return reply("I could not find reliable information for this. Please contact the Scholarship Office.",
                     "escalated", next_action="Contact the Scholarship Office")

    items = checklist(student_id, scholarship)
    problems = [i for i in items if i[1] != "OK"]
    context = (f"STUDENT: {s['name']}, {s['branch']}, language: {s['language']}\n"
               f"SCHOLARSHIP: {scholarship}\n"
               f"CURRENT SOURCE ({current[0]['source']}): {[h['text'] for h in current]}\n"
               f"OLDER SOURCE ({older[0]['source'] if older else 'none'}), superseded: {[h['text'] for h in older]}\n"
               f"CHECKLIST (decided by code): {items}\n"
               f"DEADLINE: {T['deadline']}\nQUESTION: {message}\nReply in {s['language']}.")
    try:
        text = ask_llm(SYSTEM, context)
    except Exception:                                   # fallback so the demo never breaks
        lines = [f"- {n}: {st} {why}" for n, st, why in problems] or ["- All documents look fine."]
        text = (f"Source: {current[0]['source']}\n" + "\n".join(lines) +
                f"\n\nWhat to do next: fix the items above before {T['deadline']}.")
    if problems:
        notify(student_id, "URGENT", f"{problems[0][0]} needs attention. Deadline: {T['deadline']}")
    log(student_id, cat, message, 1)
    sources = list({h["source"] for h in current + older})
    return reply(text, "action_required" if problems else "info", sources, items)
