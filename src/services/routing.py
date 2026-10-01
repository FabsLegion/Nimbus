from src.services.llm import ask_llm
from src.database.db import get_offices, get_routing_rules

class _OfficeProxy(dict):
    """Dynamic proxy for office mappings queried from the database."""
    def __getitem__(self, key):
        return get_offices()[key]
    def get(self, key, default=None):
        return get_offices().get(key, default)
    def __contains__(self, key):
        return key in get_offices()
    def items(self):
        return get_offices().items()

OFFICE = _OfficeProxy()

class _RulesProxy(list):
    """Dynamic proxy for routing rules queried from the database."""
    def __iter__(self):
        return iter(get_routing_rules())
    def __len__(self):
        return len(get_routing_rules())

RULES = _RulesProxy()

def classify_with_llm(msg: str) -> str:
    offices = get_offices()
    prompt = f"""Classify the user's inquiry into one of these specific office categories:
- PAYMENT: inquiries specifically about scholarship stipend, money credited, or bank funds
- PORTAL: technical website errors, login failures, or portal crashes
- HOSTEL: hostel room allocations, mess, or boarding facilities
- FEES: tuition fees or college admission fee receipts
- SCHOLARSHIP: scholarship rules, documents, deadlines, or any other general/unrelated inquiries

Inquiry: "{msg}"

Respond with ONLY the exact category name in capital letters (e.g. PAYMENT or SCHOLARSHIP) and nothing else."""
    try:
        res = ask_llm("You are a strict text classification model.", prompt).strip().upper()
        for cat in list(offices.keys()) + ["SCHOLARSHIP"]:
            if cat in res:
                return cat
        return "SCHOLARSHIP"
    except Exception:
        return "SCHOLARSHIP"

def classify(msg):
    m = msg.lower()
    rules = get_routing_rules()
    matched = next((cat for cat, words in rules if any(w in m for w in words)), None)
    if matched:
        return matched
    return classify_with_llm(msg)
