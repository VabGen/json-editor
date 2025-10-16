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
        return state

    try:
        local_llm = get_llm(max_tokens=768)
        logger.debug("LLM для редактирования JSON получена.")

        prompt = f"""Ты — эксперт по редактированию JSON. Следуй инструкции ПОЛНОСТЬЮ.

ИНСТРУКЦИЯ ДЛЯ ТЕБЯ:
1. Проанализируй ИСХОДНЫЙ JSON и определи, какие поля релевантны ИНСТРУКЦИИ ПОЛЬЗОВАТЕЛЯ.
2. Измени ТОЛЬКО релевантные поля.
3. Сохрани ВСЕ остальные поля без изменений.
4. Верни ТОЛЬКО валидный JSON без пояснений. НЕ используй Markdown (```json ... ```).

ИНСТРУКЦИЯ ПОЛЬЗОВАТЕЛЯ:
{state["instruction"]}

ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ:
PDF: {state.get("pdf_text", "")}
СУММАРИЗАЦИЯ: {state.get("summary", "")}

ИСХОДНЫЙ JSON:
{json.dumps(state["json_"], ensure_ascii=False, indent=2)}

ОБНОВЛЁННЫЙ JSON (только JSON, без пояснений):"""

        logger.debug(f"Сформированный промпт для LLM:\n{prompt}")

        raw_response = local_llm.invoke(prompt)
        logger.debug(f"Сырой ответ от LLM: '{raw_response}'")

        clean = raw_response.strip()

        # --- УЛУЧШЕНИЕ НАЧАЛО ---
        # 1. Проверка на пустой ответ
        if not clean:
            error_msg = "Ошибка редактирования: Модель вернула пустой ответ."
            logger.error(error_msg)
            state["error"] = error_msg
            return state  # ВАЖНО: возвращаем state, если ошибка

        # 2. Попытка извлечь JSON-объект из потенциально "обёрнутого" ответа
        # Ищем первый полноценный JSON-объект в строке
        json_match = re.search(
            r"\{.*\}", clean, re.DOTALL
        )  # re.DOTALL позволяет . совпадать с \n
        if json_match:
            potential_json_str = json_match.group(0)
            logger.debug(f"Потенциальный JSON-объект извлечен: '{potential_json_str}'")
        else:
            # Если не нашли {}, используем всю очищенную строку
            potential_json_str = clean
            logger.debug(
                f"Объект {{}} не найден, используем весь очищенный ответ: '{potential_json_str}'"
            )

        # 3. Проверка, что потенциальный JSON не пустой
        if not potential_json_str.strip():
            error_msg = "Ошибка редактирования: Модель не вернула валидный JSON. Извлечённая строка пуста."
            logger.error(error_msg)
            state["error"] = error_msg
            return state

        # 4. Попытка распарсить найденную/исходную строку как JSON
        try:
            parsed = json.loads(potential_json_str)
            logger.info("JSON успешно распарсен из ответа LLM.")
            # Если успешно, сохраняем результаты в состояние
            state["updated_json_str"] = potential_json_str
            state["final_json"] = parsed
        except json.JSONDecodeError as e:
            # Специфическая обработка ошибки парсинга JSON
            error_msg = (
                f"Ошибка редактирования: Модель не вернула валидный JSON. "
                f"Ошибка: {str(e)}. "
                f"Ответ модели (первые 300 символов): '{clean[:300]}'"
            )
            logger.error(error_msg)
            state["error"] = error_msg
        # --- УЛУЧШЕНИЕ КОНЕЦ ---

    except Exception as e:
        # Обработка любых других непредвиденных ошибок
        error_msg = f"Непредвиденная ошибка в edit_json_node: {str(e)}"
        logger.exception(error_msg)
        state["error"] = error_msg

    return state


def validate_node(state: AgentState) -> AgentState:
    """
    Проверяет финальный результат.
    Если был редактирование JSON, проверяет, не потеряны ли поля.
    Если была суммаризация или объяснение, просто возвращает состояние.
    """
    # Если на предыдущих шагах была ошибка, просто передаем её дальше
    if state.get("error"):
        logger.debug("Обнаружена ошибка на предыдущем шаге, пропускаем валидацию.")
        return state

    # Если был редактирование JSON
    if state.get("final_json"):
        original = state["json_"]
        updated = state["final_json"]

        # Проверяем, не потеряны ли поля
        original_keys = set(original.keys())
        updated_keys = set(updated.keys())
        if not original_keys.issubset(updated_keys):
            missing = original_keys - updated_keys
            state["error"] = f"Потеряны поля из исходного JSON: {missing}"
            logger.error(state["error"])
            return state

        # Логируем изменённые поля (опционально)
        changed = {k: v for k, v in updated.items() if original.get(k) != v}
        logger.info(f"Изменённые поля: {list(changed.keys())}")

    # Если была суммаризация или объяснение, результат в state["summary"]
    # Валидация не требуется, просто возвращаем состояние.
    # state["summary"] может быть строкой.

    logger.debug("Валидация пройдена успешно или не требуется.")
    return state  # ВАЖНО: всегда возвращаем state


def explain_node(state: AgentState) -> AgentState:
    """
    Генерирует текстовое объяснение или анализ на основе JSON, PDF и суммаризации.
    """
    # Проверяем, была ли уже ошибка на предыдущих шагах
    if state.get("error"):
        logger.debug("Обнаружена ошибка на предыдущем шаге, пропускаем объяснение.")
        return state  # ВАЖНО: всегда возвращаем state

    try:
        local_llm = get_llm(max_tokens=512)  # Меньше токенов для краткого ответа
        logger.debug("LLM для объяснения получена.")

        # Формируем промпт для LLM
        # Передаём весь доступный контекст
        prompt = f"""Ты — эксперт по анализу данных. Ответь на вопрос пользователя ТОЛЬКО на основе предоставленного контекста.
НЕ пытайся редактировать JSON. Просто дай текстовый ответ.

ВОПРОС ПОЛЬЗОВАТЕЛЯ:
{state["instruction"]}

КОНТЕКСТ:
ИСХОДНЫЙ JSON:
{json.dumps(state["json_"], ensure_ascii=False, indent=2)}

PDF ТЕКСТ:
{state.get("pdf_text", "Нет PDF")}

СУММАРИЗАЦИЯ PDF:
{state.get("summary", "Нет суммаризации")}

ОТВЕТ (только текст, без JSON, без пояснений):"""  # Уточняем формат ответа
        logger.debug(f"Сформированный промпт для объяснения.")

        # Вызываем LLM
        raw_response = local_llm.invoke(prompt)
        explanation = raw_response.strip()
        logger.debug(
            f"Сгенерированное объяснение (первые 100 символов): {explanation[:100]}..."
        )

        # Сохраняем объяснение в состоянии в поле summary
        # Это соответствует тому, как работает summarize_node
        state["summary"] = explanation
        logger.info("Объяснение успешно сгенерировано и сохранено в state['summary'].")

    except Exception as e:
        # Обработка любых других непредвиденных ошибок
        error_msg = f"Ошибка генерации объяснения: {str(e)}"
        logger.exception(error_msg)  # logger.exception записывает трассировку стека
        state["error"] = error_msg

    # ВАЖНО: всегда возвращаем state, даже если была ошибка
    return state


__all__ = [
    "analyze_request_node",
    "extract_pdf_node",
    "summarize_node",
    "edit_json_node",
    "validate_node",
    "explain_node",
]
