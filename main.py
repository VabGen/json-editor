# main.py
import os
import json
import logging
from tempfile import NamedTemporaryFile
from typing import Optional
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from fastapi import FastAPI, File, UploadFile, Form

from src.agent.graph import agent_graph
from src.agent.state import AgentState
import src.agent.nodes

logger = logging.getLogger(__name__)

# ======================
#   FastAPI
# ======================
app = FastAPI(title="Smart JSON Editor — Instruction Separate")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
)


@app.post("/process")
async def process_request(
    json_: Optional[str] = Form(None),
    instruction: Optional[str] = Form(None),
    summarization_type: Optional[str] = Form(None),
    json_schema: Optional[str] = Form(None),
    pdf_file: UploadFile = File(None),
):
    # === 1. Обработка PDF ===
    pdf_text = None
    if pdf_file and pdf_file.filename:
        if pdf_file.content_type != "application/pdf":
            raise HTTPException(400, "Поддерживаются только PDF-файлы")
        with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await pdf_file.read())
            tmp_path = tmp.name
        try:
            reader = PdfReader(tmp_path)
            extracted = "\n".join(
                page.extract_text() or "" for page in reader.pages
            ).strip()
            pdf_text = extracted if extracted else None
        finally:
            os.unlink(tmp_path)

    # === 2. Парсинг JSON и схемы ===
    data = {}
    schema = None
    if json_:
        try:
            # Используем импортированную функцию
            data = src.agent.nodes.safe_json_loads(json_)
        except ValueError as e:
            raise HTTPException(400, f"Невалидный JSON: {str(e)}")
    if json_schema:
        try:
            schema = json.loads(json_schema)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"Невалидная JSON-схема: {str(e)}")

    # === 3. Подготовка состояния ===
    # Создаём временное состояние
    initial_state_data = {
        "json_": data,
        "instruction": instruction if instruction is not None else "",
        "pdf_text": pdf_text,
        "summarization_type": summarization_type,
        "summary": None,
        "updated_json_str": None,
        "final_json": None,
        "error": None,
        "json_schema": schema,
    }

    # Если это только суммаризация, подготавливаем специальный JSON
    if summarization_type and not json_:
        initial_state_data["json_"] = {"_summary_placeholder": ""}
        initial_state_data["instruction"] = (
            "Заполни _summary_placeholder результатом суммаризации"
        )

    # Создаём TypedDict-совместимый объект
    initial_state = AgentState(**initial_state_data)
    logger.debug("Начальное состояние агента подготовлено.")

    # === 4. Запуск агента ===
    try:
        result_state = agent_graph.invoke(initial_state)
        logger.debug("Агент успешно завершил выполнение.")
    except Exception as e:
        logger.exception("Критическая ошибка при выполнении агента")
        raise HTTPException(500, f"Внутренняя ошибка агента: {str(e)}")

    # === 5. Формирование ответа ===
    if result_state.get("error"):
        logger.error(f"Ошибка агента: {result_state['error']}")
        raise HTTPException(500, result_state["error"])

    # Приоритеты ответа:
    # 1. final_json (результат редактирования)
    # 2. summary (результат суммаризации или объяснения)
    if result_state.get("final_json") is not None:
        logger.info("Возвращаем результат редактирования JSON.")
        return {"result": result_state["final_json"]}
    elif result_state.get("summary"):
        logger.info("Возвращаем результат суммаризации или объяснения.")
        return {"summary": result_state["summary"]}
    else:
        logger.warning("Агент не вернул ни final_json, ни summary.")
        return {"result": {}, "message": "Запрос обработан, но результат пуст."}
