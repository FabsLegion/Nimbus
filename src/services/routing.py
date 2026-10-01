from src.services.llm import ask_llm

RULES = [
    ("PAYMENT", ["payment", "credited", "not received", "money"]),
    ("PORTAL", ["portal crash", "login", "not loading", "website"]),
    ("HOSTEL", ["hostel"]), ("FEES", ["fee"]),
    ("DEADLINE", ["deadline", "last date"]), ("VERIFICATION", ["verification", "verified"]),
    ("RESULT", ["result"]),
    ("DOCUMENT", ["document", "certificate", "upload", "missing", "marksheet"]),
]
# Topics the assistant cannot answer from scholarship rules: send to a human office
OFFICE = {"PAYMENT": "Scholarship / Finance Office", "PORTAL": "IT Helpdesk",
          "HOSTEL": "Hostel Office", "FEES": "Accounts Section"}

VALID_CATEGORIES = ["PAYMENT", "PORTAL", "HOSTEL", "FEES", "DEADLINE", "VERIFICATION", "RESULT", "DOCUMENT", "SCHOLARSHIP"]

def classify_with_llm(msg: str) -> str:
    prompt = f"""Classify the user's inquiry into exactly one of these categories:
- PAYMENT (queries about money, stipend, scholarship funds credited, bank deposit, unpaid funds)
- PORTAL (login issues, technical glitches, portal errors, site not loading)
- HOSTEL (hostel rooms, mess, hostel accommodation)
- FEES (tuition fees, college fee payment, fee receipts)
- DEADLINE (due dates, last dates, submission timelines)
- VERIFICATION (document verification status, scrutiny, scrutiny dates)
- RESULT (scholarship selection results, merit list announcements)
- DOCUMENT (certificates, marksheets, uploads, required paperwork)
- SCHOLARSHIP (general scholarship criteria, eligibility, application process)

The inquiry may be in any language (e.g. English, Kannada, Hindi).
Inquiry: "{msg}"

Respond with ONLY the category name in capital letters (e.g. PAYMENT or SCHOLARSHIP) and nothing else."""
    try:
        res = ask_llm("You are a strict text classification model.", prompt).strip().upper()
        for cat in VALID_CATEGORIES:
            if cat in res:
                return cat
        return "SCHOLARSHIP"
    except Exception:
        return "SCHOLARSHIP"

def classify(msg):
    m = msg.lower()
    matched = next((cat for cat, words in RULES if any(w in m for w in words)), None)
    if matched:
        return matched
    return classify_with_llm(msg)

