from typing import Optional, TypedDict


class MailState(TypedDict, total=False):
    # --- input / queue ---
    emails: list[dict]          # mails still waiting to be handled
    today: str                  # fixed "now" (ISO), so date rules are reproducible
    prompt_version: str         # "v1" (before) or "v2" (after)
    source: str                 # "fake" (the fake mailbox) or "gmail" (real Gmail, label agent-test only)

    # --- the mail being handled right now ---
    current: Optional[dict]
    category: str               # what the model says the mail is
    reason: str                 # model's short explanation (Hebrew)
    valid_minutes: Optional[int]   # OTP validity, if written in the mail
    event_date: Optional[str]      # meeting date, if it is a calendar mail
    action: str                 # keep / archive / spam / trash / ask
    decided_by: str             # agent / user / rule
    propose_rule: bool          # True -> ask the user to make a permanent sender rule

    # --- output ---
    results: list[dict]         # one row per handled mail
