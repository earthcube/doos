"""LangGraph wiring for the SHACL-for-AI-outputs pipeline (PLAN.md §7).

    stage1 → stage2 → stage3 → stage4 → decide
    decide --(conforms | only-manual | no-progress | iteration==max)--> stage6 → END
    decide --(else)--> stage5 → stage3   # repair loop
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from . import nodes
from .state import PipelineState


def build_graph():
    """Compile and return the pipeline graph."""
    g = StateGraph(PipelineState)

    g.add_node("stage1", nodes.stage1)
    g.add_node("stage2", nodes.stage2)
    g.add_node("stage3", nodes.stage3)
    g.add_node("stage4", nodes.stage4)
    g.add_node("stage5", nodes.stage5)
    g.add_node("stage6", nodes.stage6)

    g.set_entry_point("stage1")
    g.add_edge("stage1", "stage2")
    g.add_edge("stage2", "stage3")
    g.add_edge("stage3", "stage4")
    g.add_conditional_edges(
        "stage4", nodes.decide, {"stage5": "stage5", "stage6": "stage6"}
    )
    g.add_edge("stage5", "stage3")   # re-validate after repair
    g.add_edge("stage6", END)

    return g.compile()
