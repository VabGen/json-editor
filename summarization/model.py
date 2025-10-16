# summarization/model.py
import torch
from functools import lru_cache
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

ABSTRACTIVE_MODEL_NAME = "IlyaGusev/rut5_base_sum_gazeta"
HEADLINES_MODEL_NAME = "IlyaGusev/rut5_base_headline_gen_telegram"
# OTHER_MODEL_NAME = "facebook/bart-base"


@lru_cache(maxsize=1)
def _load_abstractive_model():
    """
    Загрузка модели и токенизатора для абстрактивной суммаризации.
    Использует `functools.lru_cache` для однократной загрузки на процесс.
    """
    print(f"Загрузка абстрактивной модели: {ABSTRACTIVE_MODEL_NAME}...")
    try:
        model = AutoModelForSeq2SeqLM.from_pretrained(
            ABSTRACTIVE_MODEL_NAME, dtype=torch.float32
        )
        tokenizer = AutoTokenizer.from_pretrained(
            ABSTRACTIVE_MODEL_NAME, use_fast=True, legacy=False
        )
        print(f"Модель {ABSTRACTIVE_MODEL_NAME} успешно загружена.")
        return model, tokenizer
    except Exception as e:
        print(f"Ошибка при загрузке абстрактивной модели: {e}")


@lru_cache(maxsize=1)
def _load_headlines_model():
    """
    Загрузка модели и токенизатора для генерации заголовков/тезисов.
    Использует `functools.lru_cache` для однократной загрузки на процесс.
    """
    print(f"Загрузка модели для тезисов: {HEADLINES_MODEL_NAME}...")
    try:
        model = AutoModelForSeq2SeqLM.from_pretrained(
            HEADLINES_MODEL_NAME, dtype=torch.float32
        )
        tokenizer = AutoTokenizer.from_pretrained(
            HEADLINES_MODEL_NAME, use_fast=True, legacy=False
        )
        print(f"Модель {HEADLINES_MODEL_NAME} успешно загружена.")
        return model, tokenizer
    except Exception as e:
        print(f"Ошибка при загрузке модели для тезисов: {e}")
        raise


def get_abstractive_model():
    """
    Получить модель и токенизатор для абстрактивной суммаризации.
    """
    return _load_abstractive_model()


def get_headlines_model():
    """
    Получить модель и токенизатор для генерации тезисов.
    При ошибке загрузки откатывается к абстрактивной модели.
    """
    try:
        return _load_headlines_model()
    except Exception as e:
        print(f"Не удалось загрузить модель для тезисов ({HEADLINES_MODEL_NAME}): {e}")
        print("Откат к модели абстрактивной суммаризации.")
        return _load_abstractive_model()


# def get_other_model():
#     pass

print("Система моделей инициализирована.")
