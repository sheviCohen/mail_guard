"""Upload the 16 fake mails + their correct answers to LangSmith as a dataset (one time).
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
        print(f"הדאטהסט '{DATASET_NAME}' כבר קיים. לא יוצר שוב.")
        sys.exit(0)

    dataset = client.create_dataset(
        DATASET_NAME, description="16 fake emails with the expected category and action")

    examples = []
    for mail in mails:
        expected = truth["expected"][mail["id"]]
        examples.append({
            "inputs": {"mail": mail, "today": truth["reference_date"]},
            "outputs": {"category": expected["category"], "action": expected["action"]},
            "metadata": {"note": expected["note"]},
        })
    client.create_examples(dataset_id=dataset.id, examples=examples)
    print(f"נוצר הדאטהסט '{DATASET_NAME}' עם {len(examples)} דוגמאות.")


if __name__ == "__main__":
    main()
