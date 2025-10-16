# uv init  # создаст pyproject.toml
# uv add fastapi uvicorn python-multipart pypdf langchain langgraph llama-cpp-python pydantic jsonschema

# uv pip install -e .[dev]
# uv sync --all-extras


# uvicorn main:app --reload --port 8000
# uvicorn main:app --reload

# запрос через cur
# curl -X POST "http://127.0.0.1:8000/edit-json" `
#   -F "json_=@input.json" `
#   -F "instruction=поменяй name на Геннадий"

# abstractive summarization


# uv run python -m pytest
# uv run ruff check .
# uv run black .
# uv run mypy src/

# pip uninstall llama-cpp-python -y
# pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

#   1. Установите всё из requirements.txt
# uv pip install -r requirements.txt

#   2. Установите ОПТИМИЗИРОВАННУЮ llama-cpp-python
# uv pip uninstall llama-cpp-python -y
# uv pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
# uv pip show llama-cpp-python


# uv pip install -r requirements.txt

# rmdir /s %USERPROFILE%\.cache\huggingface  # очистка кэша

#  JSON
# uv add langchain langgraph langchain-community langchain-core
# uv add langchain-openai
# uv add pypdf jsonschema pydantic sse-starlette