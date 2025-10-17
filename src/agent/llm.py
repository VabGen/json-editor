# src/agent/llm.py
import os
from functools import lru_cache
from langchain_community.llms import LlamaCpp


@lru_cache(maxsize=1)
def get_llm(max_tokens: int = 256):
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
    # Определите количество физических ядер CPU
    # num_physical_cores = os.cpu_count() // 2 # Пример для HT
    num_physical_cores = 4

    llm = LlamaCpp(
        model_path=MODEL_PATH,
        # n_ctx=8192,
        n_ctx=4096,  # уменьшить, если не используем длинные промпты
        # n_threads=8, # количество физических ядер
        n_threads=num_physical_cores,
        # n_batch=512, # значения: 32, 64, 128, 256, 512
        n_batch=128,
        n_gpu_layers=-1,  # Попытаться загрузить все слои на GPU (если доступен и llama-cpp-python собран с поддержкой)
        # use_mlock=True, # если проблемы памяти
        temperature=0.0,  # для детерминированного ответа
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
        # seed=42, # Для воспроизводимости (опционально)
    )
    print(f"Модель {MODEL_PATH} загружена")
    return llm
