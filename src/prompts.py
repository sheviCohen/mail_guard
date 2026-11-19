"""Classification prompts.

v1 = "before": only the list of category names.
v2 = "after":  will be added LAST, after the "before" experiment.
"""

CATEGORIES = [
    "promotion", "phishing", "receipt", "order_update", "bill", "otp",
    "calendar", "social", "service_update", "security_alert",
    "personal", "google_group", "newsletter", "other",
]

PROMPT_V1 = """You classify emails.
Choose exactly one category from this list:
{categories}

If it is an OTP / verification code, also fill valid_minutes if the mail says how long it is valid.
If it is a calendar invitation or reminder, also fill event_date (ISO format) with the date of the event.
Write `reason` as one short sentence in Hebrew.
"""

PROMPTS = {
    "v1": PROMPT_V1.format(categories=", ".join(CATEGORIES)),
}


def format_email(mail: dict) -> str:
    """The text the model sees. Only the mail itself - never the expected answer."""
    return (
        f"From: {mail['from_name']} <{mail['from_email']}>\n"
        f"Date: {mail['date']}\n"
        f"Subject: {mail['subject']}\n\n"
        f"{mail['body']}"
    )
