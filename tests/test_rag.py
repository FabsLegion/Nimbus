from src.rag.retrieve import retrieve

def test_2026_wins_over_2025():
    current, older, _ = retrieve("income certificate", "Merit Scholarship - Undergraduate")
    assert all(h["year"] == 2026 for h in current)
    assert any(h["year"] == 2025 for h in older)
