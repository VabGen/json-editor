# import json
# import os
# from tempfile import NamedTemporaryFile
# from typing import TypedDict, Optional
# from fastapi import FastAPI, File, UploadFile, HTTPException, Form
# from fastapi.middleware.cors import CORSMiddleware
# from langchain.chains import llm
# from pydantic import BaseModel
# from pypdf import PdfReader
# from langchain_community.llms import LlamaCpp
# from langgraph.graph import StateGraph, END
# import jsonschema
# from sse_starlette import EventSourceResponse
# from summarization.summarize import abstractive_summarize, extractive_summarize
#
# # from llama_cpp import Llama, StoppingCriteria, StoppingCriteriaList
# import asyncio
#
# # app = FastAPI()
#
# # ======================
# #  Настройка LLM
# # ======================
# # MODEL_PATH = os.path.join(
# #     os.path.dirname(__file__), "src", "models", "qwen3-4b-pro-q5_k_m.gguf"
# # )
# MODEL_PATH = os.path.join(
#     os.path.dirname(__file__), "src", "models", "Qwen3-4B-Instruct-2507.Q5_K_M.gguf"
# )
# if not os.path.exists(MODEL_PATH):
#     raise RuntimeError(f"Модель не найдена: {MODEL_PATH}")
#
#
# # class JsonStoppingCriteria(StoppingCriteria):
# #     def __call__(self, tokens, logits, tokens_len) -> bool:
# #         # Останавливаемся, если видим "}" после JSON
# #         text = llm.detokenize(tokens).decode("utf-8", errors="ignore")
# #         if "}" in text and "{" in text:
# #             try:
# #                 extract_json_from_text(text)
# #                 return True
# #             except:
# #                 pass
# #         return False
#
#
# def get_llm(max_tokens: int = 96):
#     return LlamaCpp(
#         model_path=MODEL_PATH,
#         n_ctx=8192,
#         n_threads=8,
#         temperature=0.0,
#         max_tokens=max_tokens,
#         repeat_penalty=1.1,
#         top_p=0.9,
#         top_k=40,
#         stop=[
#             "\n\n",
#             "Хорошо,",
#             "Но я должен",
#             "После этого",
#             "Таким образом,",
#             "Итак,",
#             "Сначала",
#             "В данном случае",
#             "Ответ:",
#             "```",
#         ],
#         verbose=False,
#     )
#
#
# # ======================
# #  Состояние агента
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
#     """
#     Новая суммаризация через transformers + nltk (в стиле Hugging Face Course).
#     """
#     if state.get("error") or not state.get("summarization_type"):
#         return {}
#
#     # Получаем текст
#     text_to_summarize = ""
#     if state.get("pdf_text"):
#         text_to_summarize = state["pdf_text"]
#     else:
#         for key, value in state["json_"].items():
#             if isinstance(value, str) and len(value.strip()) > 50:
#                 text_to_summarize = value
#                 break
#
#     if not text_to_summarize.strip():
#         return {"error": "Нет текста для суммаризации"}
#
#     try:
#         if state["summarization_type"] == "extractive":
#             summary = extractive_summarize(text_to_summarize, num_sentences=2)
#         else:
#             summary = abstractive_summarize(text_to_summarize, max_length=64)
#         return {"summary": summary}
#     except Exception as e:
#         return {"error": f"Ошибка суммаризации: {str(e)}"}
#
#
# # ======================
# #  Узлы workflow — возвращаем изменения
# # ======================
# def analyze_request_node(state: AgentState) -> AgentState:
#     return {}
#
#
# def extract_pdf_node(state: AgentState) -> AgentState:
#     if state.get("pdf_text"):
#         # Обрезаем текст, чтобы не превысить контекст
#         text = state["pdf_text"][:2000]
#         return {"pdf_text": text}
#     return {}
#
#
# def extract_json_from_text(text: str) -> str:
#     """
#     Извлекает ПЕРВЫЙ валидный JSON из текста.
#     """
#     start = text.find("{")
#     if start == -1:
#         raise ValueError("Не найдена открывающая скобка {")
#
#     count = 0
#     for i in range(start, len(text)):
#         if text[i] == "{":
#             count += 1
#         elif text[i] == "}":
#             count -= 1
#             if count == 0:
#                 candidate = text[start : i + 1]
#                 try:
#                     json.loads(candidate)
#                     return candidate
#                 except json.JSONDecodeError:
#                     continue
#
#     raise ValueError("Не найден валидный JSON")
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
#         prompt_length = len(prompt)
#         max_toks = estimate_max_tokens(128)
#         local_llm = get_llm(max_toks)
#
#         raw_response = local_llm.invoke(prompt)
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
#     workflow.add_edge("extract_pdf", "summarize")
#     workflow.add_edge("summarize", "edit")
#     workflow.add_edge("edit", "validate")
#     workflow.add_edge("validate", END)
#
#     return workflow.compile()
#
#
# agent_graph = build_graph()
#
#
# def estimate_max_tokens(text_length: int) -> int:
#     """
#     Оценивает оптимальное max_tokens на основе длины входного текста.
#     Базовое правило: чем короче вход, тем короче выход.
#     """
#     if text_length < 500:
#         return 128  # Короткий JSON или инструкция
#     elif text_length < 2000:
#         return 256  # Средний документ
#     else:
#         return 512  # Длинный текст
#
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
#         json_: Optional[str] = Form(None),
#         instruction: Optional[str] = Form(None),
#         summarization_type: Optional[str] = Form(None),
#         json_schema: Optional[str] = Form(None),
#         pdf_file: UploadFile = File(None),
# ):
#     try:
#         # Определяем режим работы
#         has_json = json_ is not None and json_.strip() != ""
#         is_summarization_only = summarization_type is not None and not has_json
#         is_editing = has_json and instruction is not None
#
#         if not is_summarization_only and not is_editing:
#             raise HTTPException(
#                 400,
#                 "Укажите либо (json_ + instruction), либо (summarization_type + pdf_file или json_)",
#             )
#
#         # Парсим JSON и схему (если есть)
#         data = json.loads(json_) if has_json else {}
#         schema = json.loads(json_schema) if json_schema else None
#
#         # Обработка PDF
#         pdf_text = None
#         if pdf_file is not None:
#             if pdf_file.filename == "":
#                 pdf_text = None
#             elif pdf_file.content_type != "application/pdf":
#                 raise HTTPException(400, "Поддерживаются только PDF-файлы")
#             else:
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
#                     pdf_text = "\n".join(pages_text) if pages_text else None
#                     if pdf_text and not pdf_text.strip():
#                         pdf_text = None
#                 except Exception as pdf_error:
#                     raise HTTPException(400, f"Ошибка при чтении PDF: {str(pdf_error)}")
#                 finally:
#                     if os.path.exists(tmp_path):
#                         os.unlink(tmp_path)
#
#         # Если только суммаризация — создаём временный JSON для workflow
#         if is_summarization_only:
#             text_source = None
#             if pdf_text:
#                 text_source = "pdf"
#             elif has_json:
#                 for key, value in data.items():
#                     if isinstance(value, str) and len(value.strip()) > 10:
#                         text_source = f"json_field_{key}"
#                         pdf_text = value
#                         break
#
#             if not pdf_text:
#                 raise HTTPException(
#                     400,
#                     "Нет текста для суммаризации: загрузите PDF или передайте JSON с текстовым полем",
#                 )
#
#             data = {"_summary_placeholder": ""}
#             instruction = "Заполни _summary_placeholder результатом суммаризации"
#
#         # Запуск агента
#         initial_state = AgentState(
#             json_=data,
#             instruction=instruction,
#             json_schema=schema,
#             pdf_text=pdf_text,
#             summarization_type=summarization_type,
#             summary=None,
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
#         final_json = result["final_json"]
#
#         # Если только суммаризация — возвращаем только summary
#         if is_summarization_only:
#             summary_value = None
#             for value in final_json.values():
#                 if isinstance(value, str) and value.strip():
#                     summary_value = value
#                     break
#             if summary_value is None:
#                 summary_value = ""
#
#             return EditResponse(success=True, result={"summary": summary_value})
#
#         return EditResponse(success=True, result=final_json)
#
#     except json.JSONDecodeError as e:
#         raise HTTPException(400, f"Ошибка в JSON: {str(e)}")
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(500, f"Внутренняя ошибка: {str(e)}")
#
#
# @app.post("/edit-json-stream")
# async def edit_json_stream(
#         json_input: Optional[str] = Form(None, alias="json_"),
#         instruction_input: Optional[str] = Form(None),
#         summarization_type_input: Optional[str] = Form(None),
#         json_schema_input: Optional[str] = Form(None),
#         pdf_file: UploadFile = File(None),
# ):
#     async def event_generator():
#         try:
#             yield {"event": "status", "data": "Анализ запроса..."}
#             await asyncio.sleep(0.01)
#
#             has_json = json_input is not None and json_input.strip() != ""
#             is_summarization_only = (
#                     summarization_type_input is not None and not has_json
#             )
#             is_editing = has_json and instruction_input is not None
#
#             if not is_summarization_only and not is_editing:
#                 yield {
#                     "event": "error",
#                     "data": "Укажите либо (json_ + instruction), либо (summarization_type + pdf_file или json_)",
#                 }
#                 return
#
#             data = json.loads(json_input) if has_json else {}
#             schema = json.loads(json_schema_input) if json_schema_input else None
#
#             yield {"event": "status", "data": "Обработка PDF..."}
#             await asyncio.sleep(0.01)
#
#             pdf_text = None
#             if pdf_file is not None:
#                 if pdf_file.filename == "":
#                     pdf_text = None
#                 elif pdf_file.content_type != "application/pdf":
#                     yield {"event": "error", "data": "Поддерживаются только PDF-файлы"}
#                     return
#                 else:
#                     with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#                         tmp.write(await pdf_file.read())
#                         tmp_path = tmp.name
#                     try:
#                         reader = PdfReader(tmp_path)
#                         pages_text = []
#                         for page in reader.pages:
#                             text = page.extract_text()
#                             if text:
#                                 pages_text.append(text)
#                         pdf_text = "\n".join(pages_text) if pages_text else None
#                         if pdf_text and not pdf_text.strip():
#                             pdf_text = None
#                     except Exception as pdf_error:
#                         yield {
#                             "event": "error",
#                             "data": f"Ошибка при чтении PDF: {str(pdf_error)}",
#                         }
#                         return
#                     finally:
#                         if os.path.exists(tmp_path):
#                             os.unlink(tmp_path)
#
#             if is_summarization_only:
#                 text_source = None
#                 if pdf_text:
#                     text_source = "pdf"
#                 elif has_json:
#                     for key, value in data.items():
#                         if isinstance(value, str) and len(value.strip()) > 10:
#                             text_source = f"json_field_{key}"
#                             pdf_text = value
#                             break
#                 if not pdf_text:
#                     yield {"event": "error", "data": "Нет текста для суммаризации"}
#                     return
#                 data = {"_summary_placeholder": ""}
#                 effective_instruction = (
#                     "Заполни _summary_placeholder результатом суммаризации"
#                 )
#             else:
#                 effective_instruction = instruction_input
#
#             yield {"event": "status", "data": "Запуск агента..."}
#             await asyncio.sleep(0.01)
#
#             initial_state = AgentState(
#                 json_=data,
#                 instruction=effective_instruction,
#                 json_schema=schema,
#                 pdf_text=pdf_text,
#                 summarization_type=summarization_type_input,
#                 summary=None,
#                 updated_json_str=None,
#                 final_json=None,
#                 error=None,
#             )
#
#             result = agent_graph.invoke(initial_state)
#
#             if result.get("error"):
#                 yield {"event": "error", "data": result["error"]}
#             else:
#                 final_json = result["final_json"]
#                 if is_summarization_only:
#                     summary_value = ""
#                     for value in final_json.values():
#                         if isinstance(value, str) and value.strip():
#                             summary_value = value
#                             break
#                     yield {
#                         "event": "result",
#                         "data": json.dumps(
#                             {"summary": summary_value}, ensure_ascii=False
#                         ),
#                     }
#                 else:
#                     yield {
#                         "event": "result",
#                         "data": json.dumps(final_json, ensure_ascii=False),
#                     }
#
#         except Exception as e:
#             yield {"event": "error", "data": f"Внутренняя ошибка: {str(e)}"}
#
#     return EventSourceResponse(event_generator())
#
#
# from summarization.summarize import abstractive_summarize, extractive_summarize
# from summarization.utils import pdf_to_text
#
#
# class SummarizationRequest(BaseModel):
#     text: Optional[str] = None
#     summarization_type: str = "abstractive"  # "abstractive" или "extractive"
#
#
# @app.post("/summarize")
# async def summarize_endpoint(
#         request: SummarizationRequest = None, pdf_file: UploadFile = File(None)
# ):
#     # Получаем текст
#     if pdf_file:
#         text = pdf_to_text(pdf_file)
#     elif request and request.text:
#         text = request.text
#     else:
#         raise HTTPException(400, "Укажите text или загрузите pdf_file")
#
#     if not text.strip():
#         raise HTTPException(400, "Текст пуст")
#
#     # Выполняем суммаризацию
#     try:
#         if request.summarization_type == "extractive":
#             summary = extractive_summarize(text)
#         else:
#             summary = abstractive_summarize(text)
#         return {"summary": summary}
#     except Exception as e:
#         raise HTTPException(500, f"Ошибка суммаризации: {str(e)}")
