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

def classify(msg):
    m = msg.lower()
    return next((cat for cat, words in RULES if any(w in m for w in words)), "SCHOLARSHIP")
