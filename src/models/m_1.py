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
# MODEL_PATH = os.path.join(
#     os.path.dirname(__file__), "src", "models", "qwen3-4b-pro-q5_k_m.gguf"
# )
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
#     summarization_type: Optional[str]  # "extractive", "abstractive", None
#     summary: Optional[str]  # результат суммаризации
#     updated_json_str: Optional[str]  # Сырой ответ от LLM
#     final_json: Optional[dict]  # Сальдированный результат
#     error: Optional[str]  # Ошибка (если есть)
#
#
# # ======================
# #  Summarize
# # ======================
# def summarize_node(state: AgentState) -> AgentState:
#     if state.get("error") or not state.get("summarization_type"):
#         return {}
#
#     text_to_summarize = ""
#
#     # Определяем, что суммировать: PDF или поле из JSON
#     if state.get("pdf_text"):
#         text_to_summarize = state["pdf_text"]
#     else:
#         # Ищем поле для суммаризации в JSON (например, "bio", "content")
#         for key, value in state["json_"].items():
#             if isinstance(value, str) and len(value) > 100:
#                 text_to_summarize = value
#                 break
#
#     if not text_to_summarize:
#         return {"error": "Нет текста для суммаризации"}
#
#     # Обрезаем до разумного размера
#     text_to_summarize = text_to_summarize[:4000]
#
#     summarization_type = state["summarization_type"]
#
#     if summarization_type == "extractive":
#         prompt = f"""Выдели 2-3 самых важных предложения из текста. Верни ТОЛЬКО их, без изменений.
#
# Текст:
# {text_to_summarize}
#
# Ключевые предложения:"""
#     else:  # abstractive
#         prompt = f"""Создай краткое содержание текста в 1–2 предложениях. Используй свои слова.
#
# Текст:
# {text_to_summarize}
#
# Краткое содержание:"""
#
#     try:
#         raw_summary = llm.invoke(prompt)
#         clean_summary = raw_summary.strip()
#         return {"summary": clean_summary}
#     except Exception as e:
#         return {"error": f"Ошибка суммаризации: {str(e)}"}
#
#
# # ======================
# #  Узлы workflow — возвращаем ТОЛЬКО изменения
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
#                 return candidate[: i + 1]
#
#     # Если не закрыто — пробуем найти последнюю "}"
#     last_close = candidate.rfind("}")
#     if last_close != -1:
#         return candidate[: last_close + 1]
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
#         summary_context = (
#             f"\nСуммаризация текста:\n{state['summary']}"
#             if state.get("summary")
#             else ""
#         )
#         schema_note = "\nСоблюдай структуру исходного JSON."
#
#         prompt = f"""Ты — точный редактор JSON. Выполни инструкцию пользователя.
# НЕ добавляй новых полей, если не сказано явно. НЕ удаляй существующие.
# Верни ТОЛЬКО валидный JSON без пояснений.
#
# ИНСТРУКЦИЯ:
# {state['instruction']}{pdf_context}{summary_context}{schema_note}
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
#             return {
#                 "error": f"Не удалось извлечь JSON из ответа модели. Ответ:\n{clean}"
#             }
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
# #  Сборка графа
# # ======================
# def build_graph():
#     workflow = StateGraph(AgentState)
#     workflow.add_node("analyze", analyze_request_node)
#     workflow.add_node("extract_pdf", extract_pdf_node)
#     workflow.add_node("summarize", summarize_node)
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
# #   FastAPI
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
#         summarization_type: Optional[str] = Form(None),
#         json_schema: Optional[str] = Form(None),
#         pdf_file: UploadFile = File(None),
# ):
#     try:
#         # Парсим JSON и схему
#         data = json.loads(json_)
#         schema = json.loads(json_schema) if json_schema else None
#
#         # Обработка PDF: pdf_text будет либо текстом, либо None
#         pdf_text = None
#         if pdf_file is not None:
#             if pdf_file.filename == "":
#                 # Пустой файл — игнорируем
#                 pdf_text = None
#             elif pdf_file.content_type != "application/pdf":
#                 raise HTTPException(400, "Поддерживаются только PDF-файлы")
#             else:
#                 # Сохраняем временный файл и извлекаем текст
#                 with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#                     tmp.write(await pdf_file.read())
#                     tmp_path = tmp.name
#                 try:
#                     reader = PdfReader(tmp_path)
#                     pages_text = []
#                     for page in reader.pages:
#                         text = page.extract_text()
#                         if text:
#                             pages_text.append(text)
#                     pdf_text = "\n".join(pages_text) if pages_text else ""
#                     # Если текст пустой — оставляем None
#                     if not pdf_text.strip():
#                         pdf_text = None
#                 except Exception as pdf_error:
#                     raise HTTPException(400, f"Ошибка при чтении PDF: {str(pdf_error)}")
#                 finally:
#                     # Удаляем временный файл в любом случае
#                     if os.path.exists(tmp_path):
#                         os.unlink(tmp_path)
#
#         # Инициализация состояния агента
#         initial_state = AgentState(
#             json_=data,
#             instruction=instruction,
#             json_schema=schema,
#             pdf_text=pdf_text,  # Может быть None
#             summarization_type=summarization_type,
#             summary=None,
#             updated_json_str=None,
#             final_json=None,
#             error=None,
#         )
#
#         # Запуск workflow
#         result = agent_graph.invoke(initial_state)
#
#         if result.get("error"):
#             return EditResponse(success=False, error=result["error"])
#
#         return EditResponse(success=True, result=result["final_json"])
#
#     except json.JSONDecodeError as e:
#         raise HTTPException(400, f"Ошибка в JSON: {str(e)}")
#     except HTTPException:
#         raise  # Пробрасываем наши ошибки
#     except Exception as e:
#         raise HTTPException(500, f"Внутренняя ошибка: {str(e)}")
