# import json
# import os
# from tempfile import NamedTemporaryFile
# from typing import TypedDict, Optional
# from fastapi import FastAPI, File, UploadFile, HTTPException, Form
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from pypdf import PdfReader
# from langchain_community.llms import LlamaCpp
# from langgraph.graph import StateGraph, END
# import jsonschema
#
# # ======================
# # 1. Настройка LLM
# # ======================
# # MODEL_PATH = "./models/qwen3-4b-pro-q5_k_m.gguf"
# MODEL_PATH = os.path.join(os.path.dirname(__file__), "src", "models", "qwen3-4b-pro-q5_k_m.gguf")
# if not os.path.exists(MODEL_PATH):
#     raise RuntimeError(f"Модель не найдена: {MODEL_PATH}")
#
# llm = LlamaCpp(
#     model_path=MODEL_PATH,
#     n_ctx=32768,
#     n_threads=8,
#     temperature=0.0,
#     max_tokens=2048,
#     verbose=False,
# )
#
#
# # ======================
# # 2. Состояние агента
# # ======================
# class AgentState(TypedDict):
#     json_: dict  # Исходный JSON
#     instruction: str  # Инструкция отдельно
#     json_schema: Optional[dict]  # Опциональная схема
#     pdf_text: Optional[str]  # Текст из PDF
#     updated_json_str: Optional[str]  # Сырой ответ от LLM
#     final_json: Optional[dict]  # Сальдированный результат
#     error: Optional[str]  # Ошибка (если есть)
#
#
# # ======================
# # 3. Узлы workflow — возвращаем ТОЛЬКО изменения
# # ======================
#
#
# def analyze_request_node(state: AgentState) -> AgentState:
#     return {}  # ничего не меняем
#
#
# def extract_pdf_node(state: AgentState) -> AgentState:
#     if state.get("pdf_text"):
#         # Обрезаем текст, чтобы не превысить контекст
#         text = state["pdf_text"][:6000]
#         return {"pdf_text": text}
#     return {}
#
#
# def extract_json_from_text(text: str) -> str:
#     """
#     Извлекает последний блок, похожий на JSON, из текста.
#     Ищет строки между '{' и '}', удаляет комментарии и мусор.
#     """
#     # Удаляем всё до последней открывающей скобки {
#     last_open = text.rfind("{")
#     if last_open == -1:
#         raise ValueError("Не найдена открывающая скобка {")
#
#     # Берём подстроку с последней {
#     candidate = text[last_open:]
#
#     # Находим баланс скобок
#     count = 0
#     for i, char in enumerate(candidate):
#         if char == "{":
#             count += 1
#         elif char == "}":
#             count -= 1
#             if count == 0:
#                 return candidate[:i + 1]
#
#     # Если не закрыто — пробуем найти последнюю "}"
#     last_close = candidate.rfind("}")
#     if last_close != -1:
#         return candidate[:last_close + 1]
#
#     raise ValueError("Не найдена закрывающая скобка }")
#
#
# def edit_json_node(state: AgentState) -> AgentState:
#     try:
#         current_json_str = json.dumps(state["json_"], ensure_ascii=False, indent=2)
#         pdf_context = (
#             f"\nКонтекст из документа:\n{state['pdf_text']}"
#             if state.get("pdf_text")
#             else ""
#         )
#         # schema_note = (
#         #     "\nСоблюдай структуру исходного JSON."
#         #     if not state.get("json_schema")
#         #     else f"\nСХЕМА:\n{json.dumps(state['json_schema'], ensure_ascii=False, indent=2)}"
#         # )
#         schema_note = "\nСоблюдай структуру исходного JSON."
#
#         prompt = f"""Ты — точный редактор JSON. Выполни инструкцию пользователя.
# НЕ добавляй новых полей, если не сказано явно. НЕ удаляй существующие.
# Верни ТОЛЬКО валидный JSON без пояснений.
#
# ИНСТРУКЦИЯ:
# {state['instruction']}{pdf_context}{schema_note}
#
# ИСХОДНЫЙ JSON:
# {current_json_str}
#
# ОБНОВЛЁННЫЙ JSON:"""
#
#         raw_response = llm.invoke(prompt)
#         clean = raw_response.strip()
#         if clean.startswith("```json"):
#             clean = clean[7:]
#         if clean.endswith("```"):
#             clean = clean[:-3]
#         clean = clean.strip()
#
#         print(f"=== RAW LLM RESPONSE ===\n{raw_response}\n=== CLEANED ===\n{clean}\n")
#
#         if not clean:
#             return {"error": "Модель вернула пустой ответ"}
#
#         try:
#             json_candidate = extract_json_from_text(clean)
#             json.loads(json_candidate)
#             return {"updated_json_str": json_candidate}
#         except Exception as parse_error:
#             return {"error": f"Не удалось извлечь JSON из ответа модели. Ответ:\n{clean}"}
#
#     except Exception as e:
#         return {"error": f"Ошибка редактирования: {str(e)}"}
#
#
# def validate_json_node(state: AgentState) -> AgentState:
#     if state.get("error"):
#         return {}
#
#     try:
#         updated = json.loads(state["updated_json_str"])
#
#         # Валидация по схеме
#         if state.get("json_schema"):
#             jsonschema.validate(instance=updated, schema=state["json_schema"])
#
#         # Проверка: все исходные ключи на месте
#         original_keys = set(state["json_"].keys())
#         if not original_keys.issubset(set(updated.keys())):
#             missing = original_keys - set(updated.keys())
#             return {"error": f"Потеряны поля: {missing}"}
#
#         return {"final_json": updated}
#     except json.JSONDecodeError as e:
#         return {"error": f"Невалидный JSON: {str(e)}"}
#     except jsonschema.ValidationError as ve:
#         return {"error": f"Нарушена схема: {ve.message}"}
#     except Exception as e:
#         return {"error": f"Ошибка валидации: {str(e)}"}
#
#
# # ======================
# # 4. Сборка графа
# # ======================
# def build_graph():
#     workflow = StateGraph(AgentState)
#     workflow.add_node("analyze", analyze_request_node)
#     workflow.add_node("extract_pdf", extract_pdf_node)
#     workflow.add_node("edit", edit_json_node)
#     workflow.add_node("validate", validate_json_node)
#
#     workflow.set_entry_point("analyze")
#     workflow.add_edge("analyze", "extract_pdf")
#     workflow.add_edge("extract_pdf", "edit")
#     workflow.add_edge("edit", "validate")
#     workflow.add_edge("validate", END)
#
#     return workflow.compile()
#
#
# agent_graph = build_graph()
#
# # ======================
# # 5. FastAPI
# # ======================
# app = FastAPI(title="Smart JSON Editor — Instruction Separate")
#
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
# )
#
#
# class EditResponse(BaseModel):
#     success: bool
#     result: Optional[dict] = None
#     error: Optional[str] = None
#
#
# @app.post("/edit-json", response_model=EditResponse)
# async def edit_json_separate_instruction(
#         json_: str = Form(...),
#         instruction: str = Form(...),
#         json_schema: Optional[str] = Form(None),
#         pdf_file: UploadFile = File(None),
# ):
#     try:
#         data = json.loads(json_)
#         schema = json.loads(json_schema) if json_schema else None
#
#         pdf_text = None
#         if pdf_file:
#             if pdf_file.content_type != "application/pdf":
#                 raise HTTPException(400, "Только PDF")
#             with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#                 tmp.write(await pdf_file.read())
#                 tmp_path = tmp.name
#             try:
#                 reader = PdfReader(tmp_path)
#                 pdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
#             finally:
#                 os.unlink(tmp_path)
#
#         initial_state = AgentState(
#             json_=data,
#             instruction=instruction,
#             json_schema=schema,
#             pdf_text=pdf_text,
#             updated_json_str=None,
#             final_json=None,
#             error=None,
#         )
#
#         result = agent_graph.invoke(initial_state)
#
#         if result.get("error"):
#             return EditResponse(success=False, error=result["error"])
#
#         return EditResponse(success=True, result=result["final_json"])
#
#     except json.JSONDecodeError as e:
#         raise HTTPException(400, f"Ошибка в JSON: {str(e)}")
#     except Exception as e:
#         raise HTTPException(500, f"Ошибка: {str(e)}")
