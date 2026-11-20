"""Put the 24 fake mails into the real Gmail inbox, with the label agent-test, so the agent has something to sort.
Nothing is sent over the internet: the mails are inserted straight into your own mailbox.
Run:  python fill_gmail.py            (adds the mails only if there are no test mails yet)
      python fill_gmail.py --again    (adds them anyway, e.g. after the agent already sorted the first batch)
"""
import truststore
truststore.inject_into_ssl()      # must run first: NetFree filter

import argparse
import json
from pathlib import Path

from src import gmail_client

FAKE_EMAILS = Path(__file__).resolve().parent / "data" / "fake_emails.json"


def main():
    parser = argparse.ArgumentParser(description="fill Gmail with the fake test mails")
    parser.add_argument("--again", action="store_true", help="add the mails even if test mails already exist")
    args = parser.parse_args()

    existing = gmail_client.count_test_mails()
    if existing and not args.again:
        print(f"כבר יש בתיבה {existing} מיילים עם התווית agent-test. לא הוספתי כלום.")
        print("כדי להוסיף בכל זאת:  python fill_gmail.py --again")
        return

    mails = json.loads(FAKE_EMAILS.read_text(encoding="utf-8"))
    print(f"מכניס {len(mails)} מיילים לג'ימייל...")
    added = gmail_client.insert_fake_emails(mails)
    print(f"✅ נוספו {added} מיילים עם התווית agent-test. אפשר לראות אותם בתיבת הדואר הנכנס.")


if __name__ == "__main__":
    main()
