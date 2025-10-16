# src/agent/llm.py
import os
from functools import lru_cache
from langchain_community.llms import LlamaCpp

# PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# MODEL_PATH = str(
#     os.path.join(PROJECT_ROOT, "src", "models", "Qwen3-4B-Instruct-2507.Q5_K_M.gguf")
# )


@lru_cache(maxsize=1)
def get_llm(max_tokens: int = 384):
    MODEL_PATH = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "src",
        "models",
        "Qwen3-4B-Instruct-2507.Q5_K_M.gguf",
    )
    MODEL_PATH = os.path.abspath(MODEL_PATH)
    if not os.path.exists(MODEL_PATH):
        raise RuntimeError(f"Модель не найдена: {MODEL_PATH}")

    model = LlamaCpp(
        model_path=MODEL_PATH,
        n_ctx=8192,
        n_threads=8,
        temperature=0.0,
        max_tokens=max_tokens,
        repeat_penalty=1.1,
        top_p=0.9,
        top_k=40,
        stop=[
            "\n\n",
            "Хорошо,",
            "Но я должен",
            "После этого",
            "Таким образом,",
            "Итак,",
            "Сначала",
            "В данном случае",
            "Ответ:",
            "```",
        ],
        verbose=False,
    )
    print(f"Модель {model} загружена")
    return model
