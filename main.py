import truststore
truststore.inject_into_ssl()      # must run first: lets Python trust the Windows certificates (NetFree filter)

import uuid

from dotenv import load_dotenv
load_dotenv()

from langgraph.types import Command

from src.graph import build_graph

TODAY = "2026-11-19T23:00:00"     # fixed "now", the same date the expected answers were written for
PROMPT_VERSION = "v1"


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


def print_results(results: list[dict]) -> None:
    print("\n" + "=" * 60)
    print(f"{'id':<5}{'action':<9}{'by':<7}{'category':<16}subject")
    print("-" * 60)
    for r in results:
        print(f"{r['id']:<5}{r['action']:<9}{r['decided_by']:<7}{r['category']:<16}{r['subject'][:40]}")
    print(f"\nנשמר גם בקובץ data/results.json  ({len(results)} מיילים)")


def main():
    graph = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 500}

    state = graph.invoke({"today": TODAY, "prompt_version": PROMPT_VERSION}, config)

    # every time the graph stops to ask, show the question and resume with the answer
    while "__interrupt__" in state:
        answer = ask_user(state["__interrupt__"][0].value)
        state = graph.invoke(Command(resume=answer), config)

    print_results(state["results"])


if __name__ == "__main__":
    main()
