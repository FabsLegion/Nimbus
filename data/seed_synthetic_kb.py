"""Generate synthetic PDF documents and ingest them via the Task A4 Knowledge Base upload & publish flow."""
import os
import sys
import fitz  # PyMuPDF
import requests
from dotenv import load_dotenv

sys.path.insert(0, os.getcwd())
load_dotenv()

BASE_URL = "http://127.0.0.1:8000"
SYNTHETIC_DIR = "data/synthetic"
os.makedirs(SYNTHETIC_DIR, exist_ok=True)

DOCUMENTS = [
    # 1. Fee Structure
    {
        "filename": "fee_structure_2025_v1.pdf",
        "scholarship_name": "Fee Structure & Payment Policy",
        "year": 2025,
        "version": 1,
        "required_documents": ["Fee Receipt", "Identity Proof"],
        "dates": {"fee_due_date": "15 August 2025", "late_fee_cutoff": "25 August 2025"},
        "offices": [{"name": "Accounts & Fee Counter", "category": "FEES"}],
        "content": [
            "Fee Structure & Payment Policy | 2025 | v1",
            "Official Tuition and Fee Regulations for Academic Year 2025-2026.",
            "Undergraduate annual tuition fee is Rs 45,000 payable in two equal installments.",
            "Late payment fee surcharge is Rs 500 if paid within 10 days of the semester start.",
            "Tuition fee waiver applies for students with annual family income under Rs 1,50,000.",
            "Payment must be made through the online fee portal or demand draft to the Accounts Office."
        ]
    },
    {
        "filename": "fee_structure_2026_v2.pdf",
        "scholarship_name": "Fee Structure & Payment Policy",
        "year": 2026,
        "version": 2,
        "required_documents": ["Fee Receipt", "Identity Proof"],
        "dates": {"fee_due_date": "15 August 2026", "late_fee_cutoff": "25 August 2026"},
        "offices": [{"name": "Accounts & Fee Counter", "category": "FEES"}],
        "content": [
            "Fee Structure & Payment Policy | 2026 | v2",
            "Official Tuition and Fee Regulations for Academic Year 2026-2027.",
            "Undergraduate annual tuition fee is Rs 60,000 payable in two equal installments.",
            "Late payment fee surcharge is Rs 1,500 if paid within 10 days of the semester start.",
            "Tuition fee waiver applies for students with annual family income under Rs 2,50,000.",
            "Payment must be made through the online fee portal or net banking to the Accounts Office."
        ]
    },

    # 2. Hostel Guidelines
    {
        "filename": "hostel_guidelines_2025_v1.pdf",
        "scholarship_name": "Campus Hostel Guidelines & Rules",
        "year": 2025,
        "version": 1,
        "required_documents": ["Hostel Admission Form", "Medical Fitness Certificate"],
        "dates": {"hostel_reporting": "20 July 2025", "room_vacating": "31 May 2026"},
        "offices": [{"name": "Hostel Warden Office", "category": "HOSTEL"}],
        "content": [
            "Campus Hostel Guidelines & Rules | 2025 | v1",
            "Residential Regulations and Code of Conduct 2025.",
            "Mandatory hostel resident curfew time is 8:30 PM for all undergraduate hostels.",
            "Refundable hostel caution deposit is Rs 5,000 at the time of room allotment.",
            "Hostel mess rebate is granted for leaves exceeding 7 consecutive days.",
            "Electrical appliances exceeding 500W are strictly prohibited in hostel rooms."
        ]
    },
    {
        "filename": "hostel_guidelines_2026_v2.pdf",
        "scholarship_name": "Campus Hostel Guidelines & Rules",
        "year": 2026,
        "version": 2,
        "required_documents": ["Hostel Admission Form", "Medical Fitness Certificate"],
        "dates": {"hostel_reporting": "25 July 2026", "room_vacating": "31 May 2027"},
        "offices": [{"name": "Hostel Warden Office", "category": "HOSTEL"}],
        "content": [
            "Campus Hostel Guidelines & Rules | 2026 | v2",
            "Residential Regulations and Code of Conduct 2026.",
            "Mandatory hostel resident curfew time is 10:00 PM for all undergraduate hostels.",
            "Refundable hostel caution deposit is Rs 10,000 at the time of room allotment.",
            "Hostel mess rebate is granted for leaves exceeding 3 consecutive days.",
            "Electrical appliances exceeding 500W are strictly prohibited in hostel rooms."
        ]
    },

    # 3. Academic Calendar
    {
        "filename": "academic_calendar_2025_v1.pdf",
        "scholarship_name": "University Academic Calendar",
        "year": 2025,
        "version": 1,
        "required_documents": ["Semester Registration Slip"],
        "dates": {"semester_start": "01 August 2025", "exam_registration": "15 November 2025", "winter_break": "15 Dec 2025"},
        "offices": [{"name": "Dean of Academic Affairs", "category": "ACADEMIC"}],
        "content": [
            "University Academic Calendar | 2025 | v1",
            "Official University Academic Schedule 2025-2026.",
            "Fall semester teaching term commences on August 1st for all degree streams.",
            "End semester examination registration deadline is November 15th.",
            "Winter break vacation period is from December 15th to January 2nd.",
            "Mid-term examination assessments will be conducted in the fourth week of September."
        ]
    },
    {
        "filename": "academic_calendar_2026_v2.pdf",
        "scholarship_name": "University Academic Calendar",
        "year": 2026,
        "version": 2,
        "required_documents": ["Semester Registration Slip"],
        "dates": {"semester_start": "16 August 2026", "exam_registration": "30 November 2026", "winter_break": "22 Dec 2026"},
        "offices": [{"name": "Dean of Academic Affairs", "category": "ACADEMIC"}],
        "content": [
            "University Academic Calendar | 2026 | v2",
            "Official University Academic Schedule 2026-2027.",
            "Fall semester teaching term commences on August 16th for all degree streams.",
            "End semester examination registration deadline is November 30th.",
            "Winter break vacation period is from December 22nd to January 10th.",
            "Mid-term examination assessments will be conducted in the second week of October."
        ]
    },

    # 4. Student FAQ
    {
        "filename": "student_faq_2025_v1.pdf",
        "scholarship_name": "General Student Policy FAQ",
        "year": 2025,
        "version": 1,
        "required_documents": ["Student Identity Card"],
        "dates": {"attendance_audit": "10 November 2025"},
        "offices": [{"name": "Student Welfare Cell", "category": "STUDENT_AFFAIRS"}],
        "content": [
            "General Student Policy FAQ | 2025 | v1",
            "University Common Ordinances and Frequently Asked Questions 2025.",
            "Minimum mandatory class attendance requirement is 75% for appearing in semester exams.",
            "Maximum library book borrowing limit is 4 books for a loan duration of 14 days.",
            "Laptop subsidy grant provides Rs 15,000 one-time financial reimbursement for eligible undergraduates.",
            "Campus health center provides free emergency consultations from 8:00 AM to 8:00 PM."
        ]
    },
    {
        "filename": "student_faq_2026_v2.pdf",
        "scholarship_name": "General Student Policy FAQ",
        "year": 2026,
        "version": 2,
        "required_documents": ["Student Identity Card"],
        "dates": {"attendance_audit": "15 November 2026"},
        "offices": [{"name": "Student Welfare Cell", "category": "STUDENT_AFFAIRS"}],
        "content": [
            "General Student Policy FAQ | 2026 | v2",
            "University Common Ordinances and Frequently Asked Questions 2026.",
            "Minimum mandatory class attendance requirement is 80% for appearing in semester exams.",
            "Maximum library book borrowing limit is 6 books for a loan duration of 21 days.",
            "Laptop subsidy grant provides Rs 25,000 one-time financial reimbursement for eligible undergraduates.",
            "Campus health center provides free emergency consultations 24 hours a day."
        ]
    },

    # 5. Need-Based Scholarship
    {
        "filename": "need_based_scholarship_2025_v1.pdf",
        "scholarship_name": "Need-Based Financial Assistance Scholarship",
        "year": 2025,
        "version": 1,
        "required_documents": ["Identity Proof", "Income Certificate", "Marksheet", "Bank Document"],
        "dates": {"application_deadline": "30 September 2025", "results_date": "20 October 2025"},
        "offices": [{"name": "Financial Aid / Scholarship Office", "category": "SCHOLARSHIP"}],
        "content": [
            "Need-Based Financial Assistance Scholarship | 2025 | v1",
            "Official University Need-Based Financial Assistance Guidelines 2025.",
            "Annual gross family income ceiling limit is Rs 2,50,000 per annum for eligibility.",
            "Annual need-based scholarship stipend amount is Rs 30,000 credited to verified student bank account.",
            "Mandatory submission documents: Identity Proof, Income Certificate, Marksheet, and Bank Document.",
            "Minimum qualifying marks in prior semester examination is 60% with no active backlogs."
        ]
    },
    {
        "filename": "need_based_scholarship_2026_v2.pdf",
        "scholarship_name": "Need-Based Financial Assistance Scholarship",
        "year": 2026,
        "version": 2,
        "required_documents": ["Identity Proof", "Income Certificate", "Marksheet", "Bank Document"],
        "dates": {"application_deadline": "30 September 2026", "results_date": "20 October 2026"},
        "offices": [{"name": "Financial Aid / Scholarship Office", "category": "SCHOLARSHIP"}],
        "content": [
            "Need-Based Financial Assistance Scholarship | 2026 | v2",
            "Official University Need-Based Financial Assistance Guidelines 2026.",
            "Annual gross family income ceiling limit is Rs 4,00,000 per annum for eligibility.",
            "Annual need-based scholarship stipend amount is Rs 50,000 credited to verified student bank account.",
            "Mandatory submission documents: Identity Proof, Income Certificate, Marksheet, and Bank Document.",
            "Minimum qualifying marks in prior semester examination is 55% with no active backlogs."
        ]
    },
]

def create_pdf(filepath: str, lines: list[str]):
    """Create a clean PDF using PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 size
    y = 60
    for i, line in enumerate(lines):
        fontsize = 14 if i == 0 else (11 if i == 1 else 10)
        page.insert_text((50, y), line, fontsize=fontsize)
        y += 24 if i <= 1 else 18
    doc.save(filepath)
    doc.close()

def seed_all():
    # 1. Login to get admin token
    passcode = os.getenv("ADMIN_PASSCODE", "nimbus_admin_2026").strip()
    resp = requests.post(f"{BASE_URL}/api/auth/admin-login", json={"passcode": passcode})
    if resp.status_code != 200:
        print(f"Failed admin login: {resp.status_code} {resp.text}")
        sys.exit(1)
    admin_token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    print("Admin authenticated successfully.")

    for item in DOCUMENTS:
        pdf_path = os.path.join(SYNTHETIC_DIR, item["filename"])
        create_pdf(pdf_path, item["content"])
        print(f"Generated PDF: {pdf_path}")

        # Upload via A4 endpoint: POST /admin/kb/upload
        with open(pdf_path, "rb") as f:
            files = {"file": (item["filename"], f, "application/pdf")}
            up_resp = requests.post(f"{BASE_URL}/admin/kb/upload", headers=headers, files=files)
        
        if up_resp.status_code != 200:
            print(f"Upload failed for {item['filename']}: {up_resp.status_code} {up_resp.text}")
            continue

        draft_data = up_resp.json()
        draft_id = draft_data["id"]
        print(f"Uploaded draft ID {draft_id} for {item['filename']}")

        # Publish via A4 endpoint: POST /admin/kb/{draft_id}/publish
        pub_payload = {
            "scholarship_name": item["scholarship_name"],
            "year": item["year"],
            "version": item["version"],
            "required_documents": item["required_documents"],
            "dates": item["dates"],
            "offices": item["offices"],
        }
        pub_resp = requests.post(
            f"{BASE_URL}/admin/kb/{draft_id}/publish",
            headers=headers,
            json=pub_payload
        )
        if pub_resp.status_code == 200:
            print(f"Successfully PUBLISHED draft {draft_id}: {item['scholarship_name']} ({item['year']} v{item['version']})")
        else:
            print(f"Failed to publish draft {draft_id}: {pub_resp.status_code} {pub_resp.text}")

if __name__ == "__main__":
    seed_all()
