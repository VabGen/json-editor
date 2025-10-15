import os
import json
from tempfile import NamedTemporaryFile
from typing import Optional
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pypdf import PdfReader
from fastapi import FastAPI, File, UploadFile, Form

from src.agent.graph import agent_graph
from src.agent.state import AgentState

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
    data = json.loads(json_) if json_ else {}
    schema = json.loads(json_schema) if json_schema else None

    # === 3. Определение режима ===
    is_summarization_only = summarization_type is not None and (
        json_ is None or json_ == ""
    )
    is_editing = json_ is not None and instruction is not None

    if not is_summarization_only and not is_editing:
        raise HTTPException(
            400,
            "Укажите либо (json_ + instruction), либо (summarization_type + pdf_file или json_)",
        )

    # === 4. Подготовка состояния ===
    if is_summarization_only:
        # Создаём временный JSON для workflow
        data = {"_summary_placeholder": ""}
        instruction = "Заполни _summary_placeholder результатом суммаризации"

    initial_state = AgentState(
        json_=data,
        instruction=instruction if instruction is not None else "",
        pdf_text=pdf_text,
        summarization_type=summarization_type,
        summary=None,
        updated_json_str=None,
        final_json=None,
        error=None,
        json_schema=schema,
    )

    # === 5. Запуск агента ===
    result = agent_graph.invoke(initial_state)

    if result.get("error"):
        raise HTTPException(500, result["error"])

    if is_summarization_only:
        summary_value = result.get("final_json", {}).get("_summary_placeholder", "")
        return {"summary": summary_value}
    else:
        return {"result": result.get("final_json")}
