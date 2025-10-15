# ======================
#  Узлы workflow
# ======================
# def extract_pdf_node(state: AgentState) -> AgentState:
#     if state.pdf_text:
#         state.pdf_text = state.pdf_text[:2000]
#     return state


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
#                 candidate = text[start: i + 1]
#                 try:
#                     json.loads(candidate)
#                     return candidate
#                 except json.JSONDecodeError:
#                     continue
#
#     raise ValueError("Не найден валидный JSON")


# def edit_json(state: AgentState) -> AgentState:
#     local_llm = get_llm(max_tokens=256)
#     # parser = JsonOutputParser()
#     prompt = ChatPromptTemplate.from_messages(
#         [
#             ("system", "Ты — точный редактор JSON..."),
#             ("human", "ИНСТРУКЦИЯ: {instruction}..."),
#         ]
#     )
#     chain = prompt | local_llm
#
#     try:
#         raw_response = chain.invoke(
#             {
#                 "instruction": state.instruction,
#                 "pdf_context": state.pdf_text or "",
#                 "summary_context": state.summary or "",
#                 "json_data": json.dumps(state.json_, ensure_ascii=False),
#             }
#         )
#         clean = raw_response.strip().removeprefix("```json").removesuffix("```").strip()
#         json_candidate = extract_json_from_text(clean)
#         state.updated_json_str = json_candidate
#         # return state
#         # return {"updated_json_str": json_candidate}
#     except Exception as e:
#         state.error = f"Ошибка: {str(e)}"
#     return state


# edit_node = RunnableLambda(edit_json)


# def validate_json_node(state: AgentState) -> AgentState:
#     if state.updated_json_str is None:
#         state.error = "Нет данных для валидации"
#         return state
#
#     try:
#         updated = json.loads(state.updated_json_str)
#         if state.json_schema:
#             jsonschema.validate(instance=updated, schema=state.json_schema)
#         original_keys = set(state.json_.keys())
#         if not original_keys.issubset(set(updated.keys())):
#             missing = original_keys - set(updated.keys())
#             state.error = f"Потеряны поля: {missing}"
#         else:
#             state.final_json = updated
#     except Exception as e:
#         state.error = f"Ошибка: {str(e)}"
#     return state


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


# -----------------------------------------------------------------------------
# @app.post("/summarize")
# async def summarize_endpoint(
#     text: Annotated[str, Form()] = "",
#     summarization_type: Annotated[str, Form()] = "abstractive",
#     pdf_file: UploadFile = File(None),
# ):
#     if pdf_file:
#         text_from_pdf = pdf_to_text(pdf_file)
#         text = text_from_pdf  # перезаписываем, если PDF есть
#     elif not text.strip():
#         raise HTTPException(400, "Укажите text или загрузите pdf_file")
#
#     initial_state = AgentState(
#         json_={},
#         instruction="",
#         pdf_text=text,
#         summarization_type=summarization_type,
#         summary=None,
#         updated_json_str=None,
#         final_json=None,
#         error=None,
#         json_schema=None,
#     )
#
#     result = agent_graph.invoke(initial_state)
#
#     if result.error:
#         raise HTTPException(500, result.error)
#     if result.summary is None:
#         raise HTTPException(500, "Не удалось сгенерировать резюме")
#
#     return {"summary": result.summary}
#
#
# @app.post("/edit-json")
# async def edit_json_endpoint(
#     json_data: str = Form(...),
#     instruction: str = Form(...),
#     pdf_file: UploadFile = File(None),
# ):
#     try:
#         json_dict = json.loads(json_data)
#     except json.JSONDecodeError as e:
#         raise HTTPException(400, f"Невалидный JSON: {str(e)}")
#
#     pdf_text = None
#     if pdf_file and pdf_file.filename:
#         if pdf_file.content_type != "application/pdf":
#             raise HTTPException(400, "Поддерживаются только PDF-файлы")
#     with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#         tmp.write(await pdf_file.read())
#         tmp_path = tmp.name
#     try:
#         reader = PdfReader(tmp_path)
#         extracted_text = "\n".join(
#             page.extract_text() or "" for page in reader.pages
#         ).strip()
#         pdf_text = extracted_text if extracted_text else None
#     finally:
#         os.unlink(tmp_path)
#
#     initial_state = AgentState(
#         json_=json_dict,
#         instruction=instruction,
#         pdf_text=pdf_text,
#         summarization_type=None,
#         summary=None,
#         updated_json_str=None,
#         final_json=None,
#         error=None,
#         json_schema=None,
#     )
#
#     result = agent_graph.invoke(initial_state)
#
#     if result.get("error"):
#         raise HTTPException(500, result["error"])
#     return {"result": result.get("final_json")}
# -------------------------------------------------

# @app.post("/summarize")
# async def summarize_endpoint(
#     request: Optional[SummarizationRequest] = None, pdf_file: UploadFile = File(None)
# ):
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
#     initial_state = AgentState(
#         json_={},
#         instruction="",
#         pdf_text=text,
#         summarization_type=request.summarization_type if request else "abstractive",
#         summary=None,
#         updated_json_str=None,
#         final_json=None,
#         error=None,
#         json_schema=None,
#     )
#
#     result = agent_graph.invoke(initial_state)
#
#     if result.error:
#         raise HTTPException(500, result.error)
#
#     # Возвращаем результат суммаризации
#     if result.summary is None:
#         raise HTTPException(500, "Не удалось сгенерировать резюме")
#
#     return {"summary": result.summary}
#
#
# @app.post("/edit-json")
# async def edit_json_endpoint(
#     json_data: str = Form(...),
#     instruction: str = Form(...),
#     pdf_file: UploadFile = File(None),
# ):
#     try:
#         json_dict = json.loads(json_data)
#     except json.JSONDecodeError as e:
#         raise HTTPException(400, f"Невалидный JSON: {str(e)}")
#
#     pdf_text = None
#     if pdf_file:
#         if pdf_file.content_type != "application/pdf":
#             raise HTTPException(400, "Поддерживаются только PDF-файлы")
#     with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#         tmp.write(await pdf_file.read())
#         tmp_path = tmp.name
#     try:
#         reader = PdfReader(tmp_path)
#         extracted_text = "\n".join(
#             page.extract_text() or "" for page in reader.pages
#         ).strip()
#         pdf_text = extracted_text if extracted_text else None
#     finally:
#         os.unlink(tmp_path)
#
#     initial_state = AgentState(
#         json_=json_dict,
#         instruction=instruction,
#         pdf_text=pdf_text,
#         summarization_type=None,
#         summary=None,
#         updated_json_str=None,
#         final_json=None,
#         error=None,
#         json_schema=None,
#     )
#
#     result = agent_graph.invoke(initial_state)
#
#     if result.get("error"):
#         raise HTTPException(500, result["error"])
#     return {"result": result.get("final_json")}
