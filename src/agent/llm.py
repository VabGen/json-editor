import os
from pathlib import Path
from langchain_community.llms import LlamaCpp

# ======================
#  Настройка LLM
# ======================
# .env
# MODEL_DIR=./src/models

# from dotenv import load_dotenv
# load_dotenv()
#
# import os
# from pathlib import Path
#
# MODEL_DIR = Path(os.getenv("MODEL_DIR", "src/models"))
# if not MODEL_DIR.is_absolute():
#     MODEL_DIR = Path(__file__).parent.parent.parent / MODEL_DIR
# MODEL_PATH = MODEL_DIR / "Qwen3-4B-Instruct-2507.Q5_K_M.gguf"


# MODEL_PATH = os.path.join(
#     os.path.dirname(__file__), "src", "models", "qwen3-4b-pro-q5_k_m.gguf"
# )

PROJECT_ROOT = Path(__file__).parent.parent.parent  # json-editor/
MODEL_PATH = PROJECT_ROOT / "src" / "models" / "Qwen3-4B-Instruct-2507.Q5_K_M.gguf"
if not os.path.exists(MODEL_PATH):
    raise RuntimeError(f"Модель не найдена: {MODEL_PATH}")


def get_llm(max_tokens: int = 96):
    return LlamaCpp(
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
