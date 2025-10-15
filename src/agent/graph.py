# agent/graph.py
from langgraph.graph import StateGraph, END
from src.agent.state import AgentState
from src.agent.nodes import (
    analyze_request_node,
    extract_pdf_node,
    summarize_node,
    edit_json_node,
    validate_node,
)


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("analyze", analyze_request_node)
    workflow.add_node("extract_pdf", extract_pdf_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("edit", edit_json_node)
    workflow.add_node("validate", validate_node)

    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "extract_pdf")
    workflow.add_edge("extract_pdf", "summarize")
    workflow.add_edge("summarize", "edit")
    workflow.add_edge("edit", "validate")
    workflow.add_edge("validate", END)

    return workflow.compile()


agent_graph = build_graph()
