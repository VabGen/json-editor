# nodes.py
import logging
import re
import json
import jsonschema
from src.agent.llm import get_llm
from src.agent.state import AgentState
from summarization.summarize import (
    extractive_summarize,
    abstractive_summarize,
    headlines_summarize,
)

logger = logging.getLogger(__name__)


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
                sum_type = state["summarization_type"]
                if sum_type == "extractive":
                    summary = extractive_summarize(text_to_summarize, num_sentences=2)
                elif sum_type == "headlines":
                    summary = headlines_summarize(text_to_summarize, num_headlines=3)
                else:
                    summary = abstractive_summarize(text_to_summarize, max_length=64)

                if sum_type == "headlines":
                    state["summary"] = summary.replace("\n", "\\n")
                else:
                    state["summary"] = summary.replace("\n", "\\n")

            except Exception as e:
                state["error"] = f"Ошибка суммаризации: {str(e)}"
    return state


def clean_json_string(json_str: str) -> str:
    """Удаляет пробелы, BOM и другие невидимые символы."""
    if not isinstance(json_str, str):
        raise ValueError("Ожидалась строка")
    json_str = json_str.lstrip("\ufeff")
    json_str = json_str.strip()
    return json_str


def safe_json_loads(json_str: str) -> dict:
    """Безопасно парсит JSON, даже если он дважды сериализован."""
    cleaned = clean_json_string(json_str)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            intermediate = json.loads(f'"{cleaned}"')
            return json.loads(intermediate)
        except:
            pass

    try:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            partial = cleaned[start:end]
            return json.loads(partial)
    except:
        pass

    raise ValueError(f"Невозможно распарсить JSON: {json_str[:1000]}...")


def extract_json_from_llm_response(text: str) -> str:
    """Извлекает первый валидный JSON, даже если он обрезан."""
    json_matches = re.findall(r"\{[^{}]*}", text)
    for match in json_matches:
        try:
            json.loads(match)
            return match
        except json.JSONDecodeError:
            continue

    if text.strip().startswith("{"):
        balance = 0
        for char in text:
            if char == "{":
                balance += 1
            elif char == "}":
                balance -= 1
        repaired = text + "}" * balance
        try:
            json.loads(repaired)
            return repaired
        except json.JSONDecodeError:
            pass

    return text


def edit_json_node(state: AgentState) -> AgentState:
    """
    Редактирует JSON на основе инструкции пользователя, используя LLM.
    """
    # Проверяем, была ли уже ошибка на предыдущих шагах
    if state.get("error"):
        # Если да, просто передаем состояние дальше без изменений
        return state

    try:
        # Получаем LLM с нужными параметрами
        local_llm = get_llm(max_tokens=768)
        logger.debug("LLM для редактирования JSON получена.")

        # Формируем промпт для LLM
        prompt = f"""Ты — эксперт по редактированию JSON. Следуй инструкции ПОЛНОСТЬЮ.

ИНСТРУКЦИЯ ДЛЯ ТЕБЯ:
1. Проанализируй ИСХОДНЫЙ JSON и определи, какие поля релевантны ИНСТРУКЦИИ ПОЛЬЗОВАТЕЛЯ.
2. Измени ТОЛЬКО релевантные поля.
3. Сохрани ВСЕ остальные поля без изменений.
4. Верни ТОЛЬКО валидный JSON без пояснений.

ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ:
{state["instruction"]}

ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ:
PDF: {state.get("pdf_text", "")}
СУММАРИЗАЦИЯ: {state.get("summary", "")}

ИСХОДНЫЙ JSON:
{json.dumps(state["json_"], ensure_ascii=False, indent=2)}

ОБНОВЛЁННЫЙ JSON:"""
        logger.debug(f"Сформированный промпт для LLM:\n{prompt}")

        # Вызываем LLM
        raw_response = local_llm.invoke(prompt)
        logger.debug(f"Сырой ответ от LLM: '{raw_response}'")

        # Очищаем ответ от лишних символов/пробелов
        clean = raw_response.strip()

        # Пытаемся извлечь JSON из потенциально "обёрнутого" ответа
        # Этап 1: Убираем Markdown-блоки, если есть
        if clean.startswith("```json"):
            clean = clean[7:]  # Убираем ```json
        if clean.endswith("```"):
            clean = clean[:-3]  # Убираем ```
        clean = clean.strip()

        # Этап 2: Более надежное извлечение JSON-объекта с помощью регулярного выражения
        # Ищем первый полноценный JSON-объект в строке
        json_match = re.search(r"\{.*\}", clean, re.DOTALL)
        if json_match:
            potential_json_str = json_match.group(0)
            logger.debug(f"Потенциальный JSON-объект извлечен: '{potential_json_str}'")
        else:
            # Если не нашли {}, используем всю очищенную строку
            potential_json_str = clean
            logger.debug(
                f"Объект {{}} не найден, используем весь очищенный ответ: '{potential_json_str}'"
            )

        # Этап 3: Попытка распарсить найденную/исходную строку как JSON
        if potential_json_str:
            parsed = json.loads(potential_json_str)
            logger.info("JSON успешно распарсен из ответа LLM.")
            # Если успешно, сохраняем результаты в состояние
            state["updated_json_str"] = potential_json_str
            state["final_json"] = parsed
        else:
            # Очень маловероятно, но на всякий случай
            error_msg = f"Не удалось извлечь JSON из ответа LLM. Очищенный ответ был пустым. Ответ модели: '{raw_response[:100]}...'"
            logger.error(error_msg)
            state["error"] = error_msg

    except json.JSONDecodeError as e:
        # Специфическая обработка ошибки парсинга JSON
        error_msg = (
            f"Ошибка редактирования: Модель не вернула валидный JSON. "
            f"Ошибка: {str(e)}. "
            f"Ответ модели (первые 200 символов): '{clean[:200] if 'clean' in locals() else 'N/A'}...'"
        )
        logger.error(error_msg)
        state["error"] = error_msg

    except Exception as e:
        # Обработка любых других непредвиденных ошибок
        error_msg = f"Непредвиденная ошибка в edit_json_node: {str(e)}"
        logger.exception(error_msg)  # logger.exception записывает трассировку стека
        state["error"] = error_msg

    # Возвращаем обновленное состояние
    return state


def validate_node(state: AgentState) -> AgentState:
    if state.get("error"):
        return state

    if state.get("final_json"):
        original = state["json_"]
        updated = state["final_json"]

        if not set(original.keys()).issubset(set(updated.keys())):
            state["error"] = "Потеряны поля из исходного JSON"
            return state

        changed = {k: v for k, v in updated.items() if original.get(k) != v}
        print(f"Изменённые поля: {list(changed.keys())}")

    elif state.get("summary"):
        pass

    return state


__all__ = [
    "analyze_request_node",
    "extract_pdf_node",
    "summarize_node",
    "edit_json_node",
    "validate_node",
]
