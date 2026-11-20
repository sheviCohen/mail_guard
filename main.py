import truststore
truststore.inject_into_ssl()      # must run first: lets Python trust the Windows certificates (NetFree filter)

import argparse
import uuid

from dotenv import load_dotenv
load_dotenv()

from langgraph.types import Command

from src.graph import build_graph
from src.nodes import results_file

TODAY = "2026-11-19T23:00:00"     # fixed "now", the same date the expected answers were written for
PROMPT_VERSION = "v2"                 # the improved prompt (won the before/after experiment)


def ask_user(question: dict) -> str:
    """Show the interrupt payload in the terminal and read the user's answer."""
    print("\n" + "=" * 60)
    if question["type"] == "choose_action":
        print("🤔 הסוכן לא בטוח לגבי המייל הזה:")
        print(f"   שולח:  {question['from']}")
        print(f"   נושא:  {question['subject']}")
        print(f"   תוכן:  {question['preview']}...")
        print(f"   סיבה:  {question['reason']}")
        options = question["options"]
        answer = ""
        while answer not in options:
            answer = input(f"   מה לעשות? {' / '.join(options)}: ").strip().lower()
        return answer
    # confirm_rule
    print(f"📌 {question['from']}")
    print(f"   {question['question']}")
    return input("   > ").strip()


def print_results(results: list[dict], file_name: str) -> None:
    print("\n" + "=" * 60)
    print(f"{'id':<5}{'action':<9}{'by':<7}{'category':<16}subject")
    print("-" * 60)
    for r in results:
        print(f"{r['id'][:4]:<5}{r['action']:<9}{r['decided_by']:<7}{r['category']:<16}{r['subject'][:40]}")
        if r.get("applied") and r["applied"] != "נרשם":
            print(f"     ↳ {r['applied']}")            # Gmail: what was really done (or would be, in dry run)
    print(f"\nנשמר גם בקובץ data/{file_name}  ({len(results)} מיילים)")


def main():
    parser = argparse.ArgumentParser(description="mail_guard - sorts a mailbox")
    parser.add_argument("--gmail", action="store_true",
                        help="work on real Gmail (only mails labelled agent-test) instead of the fake mailbox")
    args = parser.parse_args()

    if args.gmail:
        from src.gmail_client import is_dry_run
        print("📬 ג'ימייל אמיתי, רק מיילים עם התווית agent-test.")
        if is_dry_run():
            print("🧪 מצב בדיקה: הסוכן רק מדווח מה היה עושה, ולא מזיז אף מייל.")
        inputs = {"source": "gmail", "prompt_version": PROMPT_VERSION}       # "today" = the real date
    else:
        inputs = {"source": "fake", "today": TODAY, "prompt_version": PROMPT_VERSION}

    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 500}

    state = graph.invoke(inputs, config)

    # every time the graph stops to ask, show the question and resume with the answer
    while "__interrupt__" in state:
        answer = ask_user(state["__interrupt__"][0].value)
        state = graph.invoke(Command(resume=answer), config)

    print_results(state["results"], results_file(inputs["source"]))


if __name__ == "__main__":
    main()
