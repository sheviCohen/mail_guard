"""Upload the fake mails + their correct answers to LangSmith as a dataset.
Safe to run again: only mails that are not in the dataset yet are added.
Run from the project folder:  python evals/create_dataset.py
"""
import truststore
truststore.inject_into_ssl()

import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from langsmith import Client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATASET_NAME = "mail_guard_emails"


def main():
    mails = json.loads((ROOT / "data" / "fake_emails.json").read_text(encoding="utf-8"))
    truth = json.loads((ROOT / "evals" / "expected_actions.json").read_text(encoding="utf-8"))

    client = Client()
    if client.has_dataset(dataset_name=DATASET_NAME):
        dataset = client.read_dataset(dataset_name=DATASET_NAME)
        # already uploaded mails (by id) are skipped, so running this again only adds new mails
        existing = {ex.inputs["mail"]["id"] for ex in client.list_examples(dataset_id=dataset.id)}
    else:
        dataset = client.create_dataset(
            DATASET_NAME, description="Fake emails with the expected category and action")
        existing = set()

    examples = []
    for mail in mails:
        if mail["id"] in existing:
            continue
        expected = truth["expected"][mail["id"]]
        examples.append({
            "inputs": {"mail": mail, "today": truth["reference_date"]},
            "outputs": {"category": expected["category"], "action": expected["action"]},
            "metadata": {"note": expected["note"]},
        })
    if not examples:
        print(f"אין מיילים חדשים. בדאטהסט '{DATASET_NAME}' יש כבר {len(existing)} דוגמאות.")
        sys.exit(0)
    client.create_examples(dataset_id=dataset.id, examples=examples)
    print(f"נוספו {len(examples)} דוגמאות. סך הכל בדאטהסט: {len(existing) + len(examples)}.")


if __name__ == "__main__":
    main()
