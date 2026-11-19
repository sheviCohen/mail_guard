from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from src import nodes
from src.state import MailState


def build_graph():
    g = StateGraph(MailState)

    for name in ["load_emails", "pick_next", "apply_sender_rule", "classify", "decide_action",
                 "ask_human", "record_decision", "propose_rule", "apply_action", "finish"]:
        g.add_node(name, getattr(nodes, name))

    # fixed edges
    g.add_edge(START, "load_emails")
    g.add_edge("load_emails", "pick_next")
    g.add_edge("classify", "decide_action")
    g.add_edge("ask_human", "record_decision")
    g.add_edge("apply_sender_rule", "apply_action")
    g.add_edge("propose_rule", "apply_action")
    g.add_edge("finish", END)

    # conditional edges (branches + the loop)
    g.add_conditional_edges("pick_next", nodes.route_after_pick, ["apply_sender_rule", "classify"])
    g.add_conditional_edges("decide_action", nodes.route_after_decide, ["ask_human", "apply_action"])
    g.add_conditional_edges("record_decision", nodes.route_after_record, ["propose_rule", "apply_action"])
    g.add_conditional_edges("apply_action", nodes.route_after_apply, ["pick_next", "finish"])

    # the checkpointer saves the state, so the graph can stop (interrupt) and continue later
    return g.compile(checkpointer=InMemorySaver())
