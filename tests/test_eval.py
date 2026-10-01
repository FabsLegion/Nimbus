"""Comprehensive Evaluation Suite for ScholarFlow.
Tests about 10 evaluation criteria:
- Correct scholarship identified
- Newest version chosen
- Policy conflict flagged
- Ambiguous name triggers clarification question
- Off-topic query handled by open chat
- Portal error explained with actionable next steps

Prints an evaluation scorecard and pass rate for judges.
"""
import os
import sys
import pytest

sys.path.insert(0, os.getcwd())

from src.database.db import get_catalog, get_required_documents
from src.rag.retrieve import retrieve
from src.services.assistant import answer, detect_conflict

RESULTS = []

def record(test_name: str, passed: bool, details: str = ""):
    RESULTS.append((test_name, passed, details))
    assert passed, details

# 1. Correct scholarship identified (Merit UG)
def test_eval_correct_scholarship_identified_merit_ug():
    catalog = get_catalog()
    assert "Merit Scholarship - Undergraduate" in catalog
    reqs = get_required_documents("Merit Scholarship - Undergraduate")
    passed = "Identity Proof" in reqs and "Marksheet" in reqs
    record("1. Correct Scholarship Identified (Merit UG)", passed, f"Reqs: {reqs}")

# 2. Correct scholarship identified (Need-Based)
def test_eval_correct_scholarship_identified_need_based():
    catalog = get_catalog()
    assert "Need-Based Financial Assistance Scholarship" in catalog
    reqs = get_required_documents("Need-Based Financial Assistance Scholarship")
    passed = "Income Certificate" in reqs and "Bank Document" in reqs
    record("2. Correct Scholarship Identified (Need-Based)", passed, f"Reqs: {reqs}")

# 3. Newest version chosen (Need-Based)
def test_eval_newest_version_chosen_need_based():
    query = "What is the annual family income ceiling limit for the Need-Based Scholarship?"
    curr, older, dist = retrieve(query, "Need-Based Financial Assistance Scholarship")
    assert len(curr) > 0, "No current chunks retrieved"
    # Newest version is 2026 v2 (4,00,000)
    current_text = " ".join(c["text"] for c in curr)
    passed = "4,00,000" in current_text and curr[0].get("year") == 2026
    record("3. Newest Version Chosen (Need-Based 2026 v2)", passed, f"Current text: {current_text[:80]}")

# 4. Newest version chosen (Fee Structure)
def test_eval_newest_version_chosen_fee_structure():
    query = "What is the undergraduate annual tuition fee?"
    curr, older, dist = retrieve(query, "Fee Structure & Payment Policy")
    assert len(curr) > 0, "No current chunks retrieved"
    # Newest version is 2026 v2 (60,000)
    current_text = " ".join(c["text"] for c in curr)
    passed = "60,000" in current_text and curr[0].get("year") == 2026
    record("4. Newest Version Chosen (Fee Structure 2026 v2)", passed, f"Current text: {current_text[:80]}")

# 5. Newest version chosen (Hostel Guidelines)
def test_eval_newest_version_chosen_hostel_curfew():
    query = "What is the hostel resident curfew time?"
    curr, older, dist = retrieve(query, "Campus Hostel Guidelines & Rules")
    assert len(curr) > 0, "No current chunks retrieved"
    # Newest version is 2026 v2 (10:00 PM)
    current_text = " ".join(c["text"] for c in curr)
    passed = "10:00 PM" in current_text and curr[0].get("year") == 2026
    record("5. Newest Version Chosen (Hostel Guidelines 2026 v2)", passed, f"Current text: {current_text[:80]}")

# 6. Conflict flagged (Need-Based Income Ceiling)
def test_eval_conflict_flagged_need_based():
    query = "What is the annual income ceiling limit for the Need-Based Scholarship?"
    curr, older, dist = retrieve(query, "Need-Based Financial Assistance Scholarship")
    conflict, unresolved = detect_conflict(query, curr, older, "Need-Based Financial Assistance Scholarship")
    passed = conflict is not None and "2,50,000" in conflict["older_rule"] and "4,00,000" in conflict["current_rule"]
    record("6. Conflict Flagged (Need-Based 2025 vs 2026)", passed, f"Conflict: {conflict}")

# 7. Conflict flagged (Hostel Curfew)
def test_eval_conflict_flagged_hostel_curfew():
    query = "What is the hostel curfew time?"
    curr, older, dist = retrieve(query, "Campus Hostel Guidelines & Rules")
    conflict, unresolved = detect_conflict(query, curr, older, "Campus Hostel Guidelines & Rules")
    passed = conflict is not None and "8:30 PM" in conflict["older_rule"] and "10:00 PM" in conflict["current_rule"]
    record("7. Conflict Flagged (Hostel Curfew 8:30 PM vs 10:00 PM)", passed, f"Conflict: {conflict}")

# 8. Conflict flagged (Tuition Fee & Late Fee)
def test_eval_conflict_flagged_fee_structure():
    query = "What is the annual tuition fee and late fee surcharge?"
    curr, older, dist = retrieve(query, "Fee Structure & Payment Policy")
    conflict, unresolved = detect_conflict(query, curr, older, "Fee Structure & Payment Policy")
    passed = conflict is not None and ("45,000" in conflict["older_rule"] or "500" in conflict["older_rule"])
    record("8. Conflict Flagged (Tuition Fee Rs 45,000 vs Rs 60,000)", passed, f"Conflict: {conflict}")

# 9. Ambiguous name triggers clarification question
def test_eval_ambiguous_name_triggers_clarification():
    # Pass chosen=None with a student that has no scholarship set
    res = answer("STU_UNASSIGNED", "Tell me about the application process and requirements.", chosen=None)
    passed = res["status"] == "clarify" and len(res.get("options", [])) >= 2
    record("9. Ambiguous Name Triggers Clarification Prompt", passed, f"Status: {res['status']}, Options: {len(res.get('options', []))}")

# 10. Off-topic query handled by open chat
def test_eval_off_topic_goes_to_open_chat():
    res = answer("STU001", "What is the capital of France and how far is it from London?", chosen="Merit Scholarship - Undergraduate")
    passed = res["status"] == "out_of_scope" and "General answer, not from scholarship documents" in (res.get("label") or res["answer"])
    record("10. Off-Topic Query Handled by Open Chat", passed, f"Status: {res['status']}")

# 11. Portal error explainer & actionable next steps
def test_eval_portal_error_explainer():
    res = answer("STU002", "DOCUMENT_INVALID", chosen="Merit Scholarship - Undergraduate", lang_override="English")
    passed = (
        res["status"] == "action_required" and
        "Likely reason" in res["answer"] and
        "What is required" in res["answer"] and
        "What to do next:" in res["answer"]
    )
    record("11. Portal Error Explainer & Actionable Guidance", passed, f"Status: {res['status']}")

def print_scorecard():
    total = len(RESULTS)
    passed = sum(1 for _, p, _ in RESULTS if p)
    pct = (passed / total * 100) if total > 0 else 0.0
    print("\n" + "=" * 68)
    print("           SCHOLARFLOW BENCHMARK EVALUATION SCORECARD")
    print("=" * 68)
    for name, p, _ in RESULTS:
        status_str = "[PASS]" if p else "[FAIL]"
        print(f"{name:<58} {status_str}")
    print("-" * 68)
    print(f"PASS RATE: {passed} / {total} ({pct:.1f}%)")
    print("=" * 68 + "\n")

if __name__ == "__main__":
    # Run tests directly
    test_eval_correct_scholarship_identified_merit_ug()
    test_eval_correct_scholarship_identified_need_based()
    test_eval_newest_version_chosen_need_based()
    test_eval_newest_version_chosen_fee_structure()
    test_eval_newest_version_chosen_hostel_curfew()
    test_eval_conflict_flagged_need_based()
    test_eval_conflict_flagged_hostel_curfew()
    test_eval_conflict_flagged_fee_structure()
    test_eval_ambiguous_name_triggers_clarification()
    test_eval_off_topic_goes_to_open_chat()
    test_eval_portal_error_explainer()
    print_scorecard()
