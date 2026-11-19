import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal, Optional

from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from src.prompts import CATEGORIES, PROMPTS, format_email
from src.state import MailState

DATA = Path(__file__).resolve().parent.parent / "data"
MODEL_NAME = "gemini-3.5-flash-lite"     # free tier: 500 requests/day, 15/minute
MAX_REQUESTS_PER_SECOND = 0.2            # 12 per minute, safely under the 15/minute limit
RULE_THRESHOLD = 3          # identical user decisions before offering a permanent rule
USER_CHOICES = ["spam", "trash", "keep", "archive"]


# ---------- small file helpers ----------

def read_json(name: str, default):
    path = DATA / name
    if not path.exists() or path.stat().st_size == 0:
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, data) -> None:
    (DATA / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- the model ----------

class Classification(BaseModel):
    """The exact shape we force the model to answer in."""
    category: Literal[tuple(CATEGORIES)]
    reason: str = Field(description="one short sentence in Hebrew")
    valid_minutes: Optional[int] = Field(default=None, description="OTP validity in minutes")
    event_date: Optional[str] = Field(default=None, description="calendar event date, ISO")


_llm = None


def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME, thinking_level="minimal",     # this model ignores temperature (fixed sampling)
            timeout=60,          # give up on a call that takes more than a minute
            max_retries=2,       # retry a failed call at most twice, instead of waiting "forever"
            rate_limiter=InMemoryRateLimiter(requests_per_second=MAX_REQUESTS_PER_SECOND),
        )
    return _llm


def classify_email(mail: dict, prompt_version: str = "v1", use_cache: bool = True) -> dict:
    """Ask the model what kind of mail this is. Cached per (prompt version, mail id) to save calls."""
    cache = read_json("classify_cache.json", {}) if use_cache else {}
    key = f"{MODEL_NAME}:{prompt_version}:{mail['id']}"     # a different model = a fresh answer
    if key in cache:
        return cache[key]

    structured = get_llm().with_structured_output(Classification)
    result = structured.invoke([
        ("system", PROMPTS[prompt_version]),
        ("human", format_email(mail)),
    ]).model_dump()

    if use_cache:
        cache[key] = result
        write_json("classify_cache.json", cache)
    return result


# ---------- the rules table (plain code, no model) ----------

def decide(category: str, mail: dict, today: str,
           valid_minutes: Optional[int] = None, event_date: Optional[str] = None) -> str:
    """Turn a category into an action. The model never decides the action - this code does."""
    now = datetime.fromisoformat(today)
    sent = datetime.fromisoformat(mail["date"])

    if category in ("promotion", "phishing"):
        return "spam"
    if category in ("receipt", "order_update", "bill"):
        return "archive" if now - sent > timedelta(days=30) else "keep"
    if category == "otp":
        expires = sent + timedelta(minutes=valid_minutes or 24 * 60)   # default: one day
        return "archive" if now > expires else "keep"
    if category == "calendar":
        if event_date and datetime.fromisoformat(event_date) < now:
            return "archive"
        return "keep"
    if category in ("social", "service_update", "newsletter"):
        return "archive"
    if category in ("security_alert", "google_group"):
        return "keep"
    if category == "personal":
        known = read_json("known_contacts.json", [])
        return "keep" if mail["from_email"].lower() in known else "ask"
    return "ask"        # "other" or anything unexpected -> the human decides


# ---------- graph nodes ----------

def load_emails(state: MailState) -> dict:
    return {"emails": read_json("fake_emails.json", []), "results": []}


def pick_next(state: MailState) -> dict:
    """Take the first mail from the queue, and clear the fields of the previous mail."""
    queue = state["emails"]
    return {
        "current": queue[0], "emails": queue[1:],
        "category": "", "reason": "", "valid_minutes": None, "event_date": None,
        "action": "", "decided_by": "", "propose_rule": False,
    }


def apply_sender_rule(state: MailState) -> dict:
    rules = read_json("sender_rules.json", {})
    sender = state["current"]["from_email"].lower()
    return {"category": "sender_rule", "action": rules[sender], "decided_by": "rule",
            "reason": "חוק קבוע שקבעת לשולח הזה"}


def classify(state: MailState) -> dict:
    try:
        result = classify_email(state["current"], state.get("prompt_version", "v1"))
    except Exception as error:
        # model unavailable (quota, no internet, timeout) -> the safe choice: let the human decide
        print(f"⚠️  המודל לא זמין ({type(error).__name__}). המייל יועבר לשאלה אלייך.")
        result = {"category": "other", "reason": "המודל לא זמין כרגע, לכן הסוכן לא סיווג את המייל",
                  "valid_minutes": None, "event_date": None}
    return {
        "category": result["category"], "reason": result["reason"],
        "valid_minutes": result["valid_minutes"], "event_date": result["event_date"],
    }


def decide_action(state: MailState) -> dict:
    action = decide(state["category"], state["current"], state["today"],
                    state.get("valid_minutes"), state.get("event_date"))
    return {"action": action, "decided_by": "agent"}


def ask_human(state: MailState) -> dict:
    """Stop the graph and wait for the user's choice. No side effects here (the node re-runs on resume)."""
    mail = state["current"]
    choice = interrupt({
        "type": "choose_action",
        "from": f"{mail['from_name']} <{mail['from_email']}>",
        "subject": mail["subject"],
        "preview": mail["body"][:120],
        "reason": state["reason"],
        "options": USER_CHOICES,
    })
    if choice not in USER_CHOICES:
        choice = "keep"          # safest default if the answer is not one of the options
    return {"action": choice, "decided_by": "user"}


def record_decision(state: MailState) -> dict:
    """Remember the user's decision per sender. After 3 identical ones -> offer a permanent rule."""
    sender = state["current"]["from_email"].lower()
    history = read_json("sender_history.json", {})
    history.setdefault(sender, []).append(state["action"])
    write_json("sender_history.json", history)

    last = history[sender][-RULE_THRESHOLD:]
    rules = read_json("sender_rules.json", {})
    propose = len(last) == RULE_THRESHOLD and len(set(last)) == 1 and sender not in rules
    return {"propose_rule": propose}


def propose_rule(state: MailState) -> dict:
    sender = state["current"]["from_email"].lower()
    answer = interrupt({
        "type": "confirm_rule",
        "from": sender,
        "action": state["action"],
        "question": f"בחרת {RULE_THRESHOLD} פעמים '{state['action']}' לשולח הזה. להפוך את זה לחוק קבוע? (yes/no)",
    })
    if str(answer).strip().lower() in ("yes", "y", "כן"):
        rules = read_json("sender_rules.json", {})
        rules[sender] = state["action"]
        write_json("sender_rules.json", rules)
    else:
        history = read_json("sender_history.json", {})
        history[sender] = []          # start counting again, so we don't nag on the next mail
        write_json("sender_history.json", history)
    return {}


def apply_action(state: MailState) -> dict:
    """In the fake mailbox, 'applying' = recording the decision. With Gmail this will move the mail."""
    mail = state["current"]
    row = {
        "id": mail["id"], "from": mail["from_email"], "subject": mail["subject"],
        "category": state["category"], "action": state["action"], "decided_by": state["decided_by"],
    }
    return {"results": state["results"] + [row]}


def finish(state: MailState) -> dict:
    write_json("results.json", state["results"])
    return {}


# ---------- routers (conditional edges) ----------

def route_after_pick(state: MailState) -> str:
    rules = read_json("sender_rules.json", {})
    return "apply_sender_rule" if state["current"]["from_email"].lower() in rules else "classify"


def route_after_decide(state: MailState) -> str:
    return "ask_human" if state["action"] == "ask" else "apply_action"


def route_after_record(state: MailState) -> str:
    return "propose_rule" if state["propose_rule"] else "apply_action"


def route_after_apply(state: MailState) -> str:
    return "pick_next" if state["emails"] else "finish"
