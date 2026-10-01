import random
from src.database.db import conn, init
init()
c = conn()
M = "Merit Scholarship - Undergraduate"
c.executemany("INSERT INTO students VALUES (?,?,?,?,?,?)", [
    ("STU001", "Demo Student", "Computer Science", "2nd Year", "English", ""),   # no scholarship chosen
    ("STU002", "Priya", "Electronics", "2nd Year", "English", M),               # wrong category upload
    ("STU003", "Arjun", "Mechanical", "3rd Year", "English", M),                # complete
    ("STU004", "Kavya", "Civil", "2nd Year", "Kannada", M),                     # asks in Kannada
])
d = [
    ("STU001", "Identity Proof", "aadhaar.pdf", "ok", ""),
    ("STU001", "Marksheet", "marksheet_sem3.pdf", "ok", ""),
    ("STU001", "Income Certificate", "income_certificate_2025.pdf", "invalid",
     "Certificate is from 2025; a current-year certificate is required"),
    ("STU002", "Identity Proof", "aadhaar.pdf", "ok", ""),
    ("STU002", "Marksheet", "marksheet.pdf", "ok", ""),
    ("STU002", "Bank Document", "bank_passbook.pdf", "ok", ""),
    ("STU002", "Caste Certificate", "income_certificate_2026.pdf", "ok", ""),
    ("STU003", "Identity Proof", "aadhaar.pdf", "ok", ""),
    ("STU003", "Income Certificate", "income_2026.pdf", "ok", ""),
    ("STU003", "Marksheet", "marksheet.pdf", "ok", ""),
    ("STU003", "Bank Document", "bank.pdf", "ok", ""),
    ("STU004", "Identity Proof", "aadhaar.pdf", "ok", ""),
    ("STU004", "Marksheet", "marksheet.pdf", "ok", ""),
]
c.executemany("INSERT INTO documents(student_id,doc_type,file_name,status,reason) VALUES (?,?,?,?,?)", d)
# fake history so the admin charts look real
cats = ["DOCUMENT"] * 13 + ["SCHOLARSHIP"] * 9 + ["DEADLINE"] * 6 + ["VERIFICATION"] * 6 + ["PAYMENT"] * 3
for cat in cats:
    c.execute("INSERT INTO queries(student_id,category,text,resolved,office) VALUES (?,?,?,?,?)",
              ("STU00%d" % random.randint(1, 4), cat, "sample question", 0 if cat == "PAYMENT" else 1, ""))
c.commit()
print("Database seeded")
