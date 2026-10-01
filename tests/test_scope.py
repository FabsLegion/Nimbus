from src.rag.retrieve import retrieve
from src.services.assistant import answer

def test_scope_guard_distances():
    # 3 on-topic questions
    on_topic = [
        "income certificate requirement",
        "application deadline",
        "which documents are required"
    ]
    for q in on_topic:
        current, older, dist = retrieve(q, "Merit Scholarship - Undergraduate")
        assert len(current) > 0
        assert dist <= 30.0, f"On-topic query '{q}' had unexpectedly high distance {dist}"

    # 3 off-topic questions
    off_topic = [
        "how to make pizza",
        "who won the football world cup",
        "what is the capital of France"
    ]
    for q in off_topic:
        _, _, dist = retrieve(q, "Merit Scholarship - Undergraduate")
        assert dist > 30.0, f"Off-topic query '{q}' had unexpectedly low distance {dist}"

def test_scope_guard_assistant_off_topic():
    # Test that off-topic queries return out_of_scope and direct to Financial Aid / Scholarship Office
    off_topic = [
        "how to make pizza",
        "who won the football world cup",
        "what is the capital of France"
    ]
    for q in off_topic:
        res = answer("STU003", q)
        assert res["status"] == "out_of_scope"
        assert "outside the scholarship rules" in res["answer"]
        assert "Financial Aid / Scholarship Office" in res["answer"]
