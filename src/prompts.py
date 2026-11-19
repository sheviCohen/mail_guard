"""Classification prompts.

v1 = "before": only the list of category names.
v2 = "after":  a definition for every category (where the borders are) + warning signs of phishing.
               Written after the "before" experiment showed where v1 gets confused.
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

PROMPT_V2 = """You classify emails for a personal mailbox assistant.
Choose exactly one category. Read the definitions carefully - the borders between them matter.

- promotion: the mail tries to SELL. Any discount, coupon code, sale or "buy now" makes it a promotion,
  even if it also contains tips or content.
- newsletter: a periodic content digest the user subscribed to (tips, articles, news)
  with NO discount, coupon or sale.
- phishing: a scam. Warning signs (one strong sign is enough):
    * the sender domain imitates a known brand but is not its real domain
      (letters replaced by digits, extra words like "-verify" or "-secure"),
    * asks to click a link and enter a password, card number or personal details,
    * threatens urgency ("your account will be blocked within 24 hours").
  A scam can also be calm and polite, with no threats at all - check the sender domain.
- security_alert: a REAL notice about account security (new sign-in, password changed)
  from the service's real domain. It never asks for a password through a link.
- receipt: proof of a payment that was ALREADY made.
- bill: a request to PAY: states an amount due and/or a payment deadline, not paid yet.
- order_update: shipping or delivery status of an order.
- otp: a one-time / verification / login code.
- calendar: a meeting invitation or a reminder of an event.
- social: AUTOMATIC notifications from a social network (likes, comments, friend requests, "who viewed you").
- personal: a message WRITTEN BY A REAL PERSON to the user, asking or telling something personal.
  This is personal even when it arrives through a social network or another platform.
- service_update: a company informs about terms, policy, statements or account changes,
  and no payment or action is required.
- google_group: a message sent through a mailing list / Google Group (googlegroups.com).
- other: none of the above, or you are not sure.

Extra fields:
- valid_minutes: only for otp, if the mail says how long the code is valid.
- event_date: only for calendar, the event date in ISO format (YYYY-MM-DDTHH:MM:SS).
- reason: one short sentence in Hebrew explaining your choice.
"""

PROMPTS = {
    "v1": PROMPT_V1.format(categories=", ".join(CATEGORIES)),
    "v2": PROMPT_V2,
}


def format_email(mail: dict) -> str:
    """The text the model sees. Only the mail itself - never the expected answer."""
    return (
        f"From: {mail['from_name']} <{mail['from_email']}>\n"
        f"Date: {mail['date']}\n"
        f"Subject: {mail['subject']}\n\n"
        f"{mail['body']}"
    )
