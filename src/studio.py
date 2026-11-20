"""Entry point for LangGraph Studio (a visual, live view of the graph in the browser).
Run from the project folder:  langgraph dev
"""
import truststore
truststore.inject_into_ssl()          # NetFree filter: trust the Windows certificates

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # so "from src..." works inside the Studio server

from src.graph import build_graph

graph = build_graph(with_checkpointer=False)    # Studio adds its own checkpointer
