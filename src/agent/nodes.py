# nodes.py
import json
import jsonschema
from src.agent.llm import get_llm
from src.agent.state import AgentState
from summarization.summarize import extractive_summarize, abstractive_summarize


def analyze_request_node(state: AgentState) -> AgentState:
    return state


def extract_pdf_node(state: AgentState) -> AgentState:
    pdf_text = state.get("pdf_text")
    if pdf_text is not None:
        state["pdf_text"] = pdf_text[:2000]
    return state


def summarize_node(state: AgentState) -> AgentState:
    if not state.get("error") and state.get("summarization_type"):
        # Получаем текст из PDF или JSON
        text_to_summarize = state.get("pdf_text") or ""
        if not text_to_summarize:
            json_data = state.get("json_")
            # Проверяем, что json_data — словарь
            if isinstance(json_data, dict):
                text_to_summarize = next(
                    (
                        v
                        for v in json_data.values()
                        if isinstance(v, str) and len(v.strip()) > 50
                    ),
                    "",
                )
            else:
                text_to_summarize = ""

        if text_to_summarize.strip():
            try:
                if state["summarization_type"] == "extractive":
                    state["summary"] = extractive_summarize(
                        text_to_summarize, num_sentences=2
                    )
                else:
                    state["summary"] = abstractive_summarize(
                        text_to_summarize, max_length=64
                    )
            except Exception as e:
                state["error"] = f"Ошибка суммаризации: {str(e)}"
    return state


def edit_json_node(state: AgentState) -> AgentState:
    if not state.get("error"):
        try:
            local_llm = get_llm(max_tokens=256)
            prompt = f"""Ты — точный редактор JSON. Выполни инструкцию.
ИНСТРУКЦИЯ: {state["instruction"]}
PDF: {state.get("pdf_text", "")}
СУММАРИЗАЦИЯ: {state.get("summary", "")}
ИСХОДНЫЙ JSON: {json.dumps(state["json_"], ensure_ascii=False)}"""

            raw_response = local_llm.invoke(prompt)
            clean = (
                raw_response.strip().removeprefix("```json").removesuffix("```").strip()
            )
            state["updated_json_str"] = clean
            state["final_json"] = json.loads(clean)
        except Exception as e:
            state["error"] = f"Ошибка редактирования: {str(e)}"
    return state


def validate_node(state: AgentState) -> AgentState:
    if not state.get("error"):
        final_json = state.get("final_json")
        json_data = state.get("json_")

        if final_json is None or json_data is None:
            state["error"] = "Отсутствуют данные для валидации"
            return state

        try:
            if state.get("json_schema"):
                jsonschema.validate(instance=final_json, schema=state["json_schema"])
            original_keys = set(json_data.keys())
            updated_keys = set(final_json.keys())
            if not original_keys.issubset(updated_keys):
                missing = original_keys - updated_keys
                state["error"] = f"Потеряны поля: {missing}"
        except Exception as e:
            state["error"] = f"Ошибка валидации: {str(e)}"
    return state


__all__ = [
    "analyze_request_node",
    "extract_pdf_node",
    "summarize_node",
    "edit_json_node",
    "validate_node",
]
