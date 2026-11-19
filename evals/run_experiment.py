"""Run one experiment: classify every mail in the dataset with a given prompt version, and score it.
Run from the project folder:  python evals/run_experiment.py v1
"""
import truststore
truststore.inject_into_ssl()

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))          # so "from src..." works when running this file directly

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from langsmith import Client

from src.nodes import classify_email, decide

DATASET_NAME = "mail_guard_emails"
VERSION = sys.argv[1] if len(sys.argv) > 1 else "v1"


# ---------- what we test: the model's category + the code's decision ----------

def target(inputs: dict) -> dict:
    mail = inputs["mail"]
    result = classify_email(mail, VERSION, use_cache=False)      # a real call, so it shows up as a trace
    action = decide(result["category"], mail, inputs["today"],
                    result["valid_minutes"], result["event_date"])
    return {"category": result["category"], "action": action, "reason": result["reason"]}


# ---------- evaluators: each one gives a score to one example ----------

def action_correct(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "action_correct", "score": int(outputs["action"] == reference_outputs["action"])}


def category_correct(outputs: dict, reference_outputs: dict) -> dict:
    return {"key": "category_correct", "score": int(outputs["category"] == reference_outputs["category"])}


def no_dangerous_error(outputs: dict, reference_outputs: dict) -> dict:
    """The mistakes that really hurt:
    1. an important mail (keep / ask) was moved out of the inbox (spam / archive),
    2. a scam or ad (spam) was left in the inbox (keep)."""
    expected, got = reference_outputs["action"], outputs["action"]
    lost_important = expected in ("keep", "ask") and got in ("spam", "archive")
    scam_left_in = expected == "spam" and got == "keep"
    return {"key": "no_dangerous_error", "score": int(not (lost_important or scam_left_in))}


def main():
    results = Client().evaluate(
        target,
        data=DATASET_NAME,
        evaluators=[action_correct, category_correct, no_dangerous_error],
        experiment_prefix=f"prompt-{VERSION}",
        metadata={"prompt_version": VERSION},
        max_concurrency=1,                  # one mail at a time, to stay inside the free-tier limits
    )

    totals, mistakes = {}, []
    for row in results:
        mail_id = row["example"].inputs["mail"]["id"]
        for ev in row["evaluation_results"]["results"]:
            totals.setdefault(ev.key, []).append(ev.score)
            if ev.key == "action_correct" and ev.score == 0:
                out = row["run"].outputs
                mistakes.append(f"{mail_id}: expected {row['example'].outputs['action']}, "
                                f"got {out['action']} ({out['category']})")

    print(f"\n===== prompt {VERSION} =====")
    for key, scores in totals.items():
        print(f"{key:<20} {sum(scores)}/{len(scores)}  ({100 * sum(scores) / len(scores):.0f}%)")
    print("\nmistakes:" if mistakes else "\nno mistakes")
    for m in mistakes:
        print("  " + m)


if __name__ == "__main__":
    main()
