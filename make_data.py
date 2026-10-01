import json, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

T = json.load(open("data/master_timeline.json"))
os.makedirs("data/scholarships", exist_ok=True)

def pdf(path, lines):
    c = canvas.Canvas(path, pagesize=A4)
    y = 800
    for line in lines:          # keep each line short so it fits the page
        c.drawString(50, y, line)
        y -= 22
    c.save()

# First line of every PDF must be:  Name | year | vN
pdf("data/scholarships/merit_ug_2025_v1.pdf", [
    "Merit Scholarship - Undergraduate | 2025 | v1",
    "Required: Identity Proof, Income Certificate, Marksheet, Bank Document.",
    "Income Certificate: a previous-year certificate is accepted.",
])
pdf("data/scholarships/merit_ug_2026_v3.pdf", [
    "Merit Scholarship - Undergraduate | 2026 | v3",
    "Required: Identity Proof, Income Certificate, Marksheet, Bank Document.",
    "Income Certificate: a current-year certificate is required.",
    "Previous-year certificates are not accepted.",
    f"Application deadline: {T['deadline']}.",
    f"Verification: {T['verification']}. Results: {T['results']}.",
])
pdf("data/scholarships/merit_special_2026_v2.pdf", [
    "Merit Scholarship - Special Category | 2026 | v2",
    "Required: Identity Proof, Category Certificate, Marksheet.",
    "Income Certificate is not required for this scholarship.",
    f"Application deadline: {T['deadline']}.",
])
print("PDFs created")
