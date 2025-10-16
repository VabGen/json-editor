# agent/graph.py
import logging

from langgraph.graph import StateGraph, END
from src.agent.state import AgentState
from src.agent.nodes import (
    analyze_request_node,
    extract_pdf_node,
    summarize_node,
    edit_json_node,
    explain_node,
    validate_node,
)


def should_edit_json(state: AgentState) -> str:
    """
    Определяет, нужно ли запускать редактирование JSON.
    """
    json_data = state.get("json_")
    instruction = state.get("instruction")

    if json_data and instruction:
        return "edit"
    else:
        return "validate"


def route_after_summarize(state: AgentState) -> str:
    """
    Определяет маршрут после узла summarize.
    """
    logger = logging.getLogger(__name__)  # Для логирования внутри функции
    logger.debug(
        f"Определение маршрута после summarize. State keys: {list(state.keys())}"
    )

    json_data = state.get("json_")
    instruction = state.get("instruction", "").strip()
    summarization_type = state.get("summarization_type")

    # Сценарий 1: Только суммаризация PDF/JSON
    if summarization_type and not json_data and not instruction:
        logger.debug("Маршрут: validate (только суммаризация)")
        return "validate"

    # Сценарий 2: Есть JSON и инструкция
    if json_data and instruction:
        # Определяем тип инструкции
        instruction_lower = instruction.lower()
        explanation_keywords = [
            "о чем",
            "что в",
            "опиши",
            "расскажи",
            "объясни",
            "структура",
            "анализ",
            "дай сведения",
            "что содержится",
            "что находится",
        ]
        is_explanation = any(
            keyword in instruction_lower for keyword in explanation_keywords
        )

        if is_explanation:
            logger.debug("Маршрут: explain (объяснение/анализ)")
            return "explain"  # Направляем в новый узел
        else:
            logger.debug("Маршрут: edit (редактирование)")
            return "edit"  # Направляем в узел редактирования

    # Сценарий 3: По умолчанию
    logger.warning(
        f"Не удалось определить маршрут. json_: {bool(json_data)}, instruction: '{instruction}', summarization_type: {summarization_type}. Маршрут: validate."
    )
    return "validate"


def build_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("analyze", analyze_request_node)
    workflow.add_node("extract_pdf", extract_pdf_node)
    workflow.add_node("summarize", summarize_node)
    workflow.add_node("edit", edit_json_node)
    workflow.add_node("explain", explain_node)  # Добавляем новый узел
    workflow.add_node("validate", validate_node)

    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "extract_pdf")
    workflow.add_edge("extract_pdf", "summarize")

    # Используем условный роутинг после summarize
    workflow.add_conditional_edges(
        "summarize",
        route_after_summarize,
        {"edit": "edit", "explain": "explain", "validate": "validate"},
    )

    # Оба пути редактирования и объяснения ведут к валидации/финальному результату
    workflow.add_edge("edit", "validate")
    workflow.add_edge("explain", "validate")
    workflow.add_edge("validate", END)

    compiled_graph = workflow.compile()
    logger = logging.getLogger(__name__)
    logger.info("Граф агента успешно скомпилирован.")
    return compiled_graph


agent_graph = build_graph()
