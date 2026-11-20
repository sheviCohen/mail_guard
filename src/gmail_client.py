"""Connection to a real Gmail inbox.

Safety rules (decided at the start of the project):
- The agent acts ONLY on mails that carry the label `agent-test`. Real mail is never touched.
- Permission scope `gmail.modify`: can move mails and send them to the trash, but can NOT delete forever.
- DRY RUN by default: the agent only reports what it WOULD do. To really move mails,
  set MAIL_GUARD_DRY_RUN=false in the .env file.
- Every mail the agent handles gets a decision label (for example "סוכן/ספאם"), also in dry run,
  so the decision can be seen on the mail itself in Gmail. A label never moves or deletes a mail.
Setup guide: docs/gmail_setup.md
"""
import base64
import os
from datetime import datetime
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import format_datetime, parseaddr, parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS = ROOT / "credentials.json"     # downloaded from Google Cloud (never committed)
TOKEN = ROOT / "token.json"                 # created after the first sign-in (never committed)
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
LABEL_NAME = "agent-test"

# what each action means in Gmail: which labels to add / remove
LABEL_CHANGES = {
    "archive": {"removeLabelIds": ["INBOX"]},
    "spam": {"addLabelIds": ["SPAM"], "removeLabelIds": ["INBOX"]},
}

# the label that shows the agent's decision on the mail itself (nested under one parent label)
DECISION_PARENT = "סוכן"
DECISION_LABELS = {
    "keep": "סוכן/להשאיר",
    "archive": "סוכן/ארכיון",
    "spam": "סוכן/ספאם",
    "trash": "סוכן/פח",
    "ask": "סוכן/שאלה",
}

_service = None
_label_ids = {}        # label name -> label id, filled once per run


def is_dry_run() -> bool:
    return os.getenv("MAIL_GUARD_DRY_RUN", "true").strip().lower() != "false"


# ---------- sign-in ----------

def get_service():
    """Sign in to Gmail once, and keep the connection. The first time, a browser window asks for permission."""
    global _service
    if _service is not None:
        return _service

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDENTIALS.exists():
                raise FileNotFoundError(
                    "חסר הקובץ credentials.json בתיקיית הפרויקט. ההוראות: docs/gmail_setup.md")
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")

    _service = build("gmail", "v1", credentials=creds)
    return _service


def get_label_id(name: str = LABEL_NAME) -> str:
    """The id of a label by its name. Creates the label if it does not exist yet."""
    if not _label_ids:
        for label in get_service().users().labels().list(userId="me").execute().get("labels", []):
            _label_ids[label["name"]] = label["id"]
    if name not in _label_ids:
        created = get_service().users().labels().create(
            userId="me",
            body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
        ).execute()
        _label_ids[name] = created["id"]
    return _label_ids[name]


def mark_decision(message_id: str, action: str) -> None:
    """Put the decision label on the mail, and remove an older decision label from a previous run."""
    get_label_id(DECISION_PARENT)                       # the parent first, so Gmail shows the labels nested
    new_label = get_label_id(DECISION_LABELS[action])
    old_labels = [_label_ids[n] for n in DECISION_LABELS.values() if n in _label_ids and _label_ids[n] != new_label]
    get_service().users().messages().modify(
        userId="me", id=message_id,
        body={"addLabelIds": [new_label], "removeLabelIds": old_labels},
    ).execute()


# ---------- filling the inbox with fake mails ----------

def count_test_mails() -> int:
    resp = get_service().users().messages().list(userId="me", labelIds=[get_label_id()]).execute()
    return resp.get("resultSizeEstimate", 0)


def insert_fake_emails(mails: list[dict]) -> int:
    """Put the fake mails straight into the inbox, as if they arrived. Nothing is sent over the internet."""
    service = get_service()
    me = service.users().getProfile(userId="me").execute()["emailAddress"]
    for mail in mails:
        msg = EmailMessage()
        msg["From"] = f'{mail["from_name"]} <{mail["from_email"]}>'
        msg["To"] = me
        msg["Subject"] = mail["subject"]
        msg["Date"] = format_datetime(datetime.fromisoformat(mail["date"]).astimezone())
        msg["X-Mail-Guard-Id"] = mail["id"]
        msg.set_content(mail["body"])
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().insert(
            userId="me",
            body={"raw": raw, "labelIds": ["INBOX", "UNREAD", get_label_id()]},
            internalDateSource="dateHeader",       # keep the date from the mail, not "now"
        ).execute()
    return len(mails)


# ---------- reading ----------

def _decode(value: str) -> str:
    """Headers with Hebrew arrive encoded (=?utf-8?b?...?=). This turns them back into text."""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _body_text(payload: dict) -> str:
    """Find the plain-text part of the mail and decode it."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace").strip()
    for part in payload.get("parts", []) or []:
        text = _body_text(part)
        if text:
            return text
    return ""


def fetch_emails(max_results: int = 50) -> list[dict]:
    """Read the mails that are in the inbox AND carry the agent-test label, in the same shape as fake_emails.json."""
    service = get_service()
    resp = service.users().messages().list(
        userId="me", labelIds=[get_label_id(), "INBOX"], maxResults=max_results).execute()

    mails = []
    for ref in resp.get("messages", []):
        full = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in full["payload"].get("headers", [])}
        name, address = parseaddr(_decode(headers.get("from", "")))
        if "date" in headers:
            date = parsedate_to_datetime(headers["date"])
        else:
            date = datetime.fromtimestamp(int(full["internalDate"]) / 1000)
        if date.tzinfo:
            date = date.astimezone().replace(tzinfo=None)    # local time, without timezone, like the fake mails
        mails.append({
            "id": full["id"],
            "from_name": name or address,
            "from_email": address,
            "subject": _decode(headers.get("subject", "")),
            "body": _body_text(full["payload"]) or full.get("snippet", ""),
            "date": date.isoformat(timespec="seconds"),
        })
    mails.sort(key=lambda m: m["date"])
    return mails


# ---------- acting ----------

def apply_action(message_id: str, action: str) -> str:
    """Label the mail with the decision, then move it. Returns a short Hebrew description of what happened."""
    if action not in DECISION_LABELS:
        raise ValueError(f"פעולה לא מוכרת: {action}")

    service = get_service()
    msg = service.users().messages().get(userId="me", id=message_id, format="minimal").execute()
    if get_label_id() not in msg.get("labelIds", []):
        # the safety fence: never touch a mail without the test label, whatever the agent decided
        raise PermissionError("סירוב: למייל אין את התווית agent-test")

    mark_decision(message_id, action)          # also in dry run: a label only marks, it moves nothing
    label = DECISION_LABELS[action]

    if action in ("keep", "ask"):
        return f"נשאר בתיבה, סומן {label}"
    if is_dry_run():
        return f"מצב בדיקה: סומן {label}, לא הוזז"
    if action == "trash":
        service.users().messages().trash(userId="me", id=message_id).execute()   # recoverable for 30 days
    else:
        service.users().messages().modify(userId="me", id=message_id, body=LABEL_CHANGES[action]).execute()
    return f"בוצע: {action}, סומן {label}"
