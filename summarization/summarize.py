# summarization/summarize.py
import nltk
from summarization.model import get_abstractive_model, get_headlines_model

try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")


def extractive_summarize(text: str, num_sentences: int = 2) -> str:
    """Извлекает первые N предложений из текста."""
    from nltk.tokenize import sent_tokenize

    sentences = sent_tokenize(text)
    return " ".join(sentences[:num_sentences]).strip()


def abstractive_summarize(text: str, max_length: int = 64) -> str:
    """
    Создаёт краткое содержание текста в 1–2 предложениях.
    Использует модель, подходящую для абстрактивной суммаризации.
    """
    model, tokenizer = get_abstractive_model()

    prompt = f"""Выдели 1-2 самых важных предложения из текста.
    НЕ ДОБАВЛЯЙ информацию, которой нет в тексте.
    НЕ ПИШИ "в этом году", "в Украине" и другие клише — только то, что есть в тексте.

    Текст:
    {text}

    Ключевые предложения:"""

    inputs = tokenizer(
        [prompt],
        max_length=512,
        truncation=True,
        return_tensors="pt",
    )

    summary_ids = model.generate(
        inputs["input_ids"],
        attention_mask=inputs["attention_mask"],
        max_length=max_length + 10,
        min_length=10,
        length_penalty=1.2,
        num_beams=4,
        early_stopping=True,
    )

    summary = tokenizer.decode(summary_ids[0], skip_special_tokens=True).strip()

    if summary.lower().startswith("ключевые предложения:"):
        summary = summary[len("ключевые предложения:") :].strip()
    if "текст:" in summary.lower():
        parts = summary.split("текст:", 1)
        if len(parts) > 1:
            summary = parts[0].strip()

    return summary


def headlines_summarize(text: str, num_headlines: int = 3) -> str:
    """
    Создаёт список из N ключевых тезисов/пунктов из текста.
    Использует модель, заточенную под генерацию заголовков или тезисов.
    """
    model, tokenizer = get_headlines_model()

    prompt = f"""headline
{text}"""

    inputs = tokenizer(
        [prompt],
        max_length=512,
        truncation=True,
        return_tensors="pt",
    )

    summary_ids = model.generate(
        inputs["input_ids"],
        attention_mask=inputs["attention_mask"],
        max_length=128,
        num_beams=4,
        length_penalty=1.0,
        early_stopping=True,
        num_return_sequences=num_headlines,
    )

    # Декодируем все сгенерированные варианты
    headlines_list = [
        tokenizer.decode(
            g, skip_special_tokens=True, clean_up_tokenization_spaces=True
        ).strip()
        for g in summary_ids
    ]

    seen = set()
    unique_headlines = []
    for headline in headlines_list:
        if headline and headline not in seen:
            headline_clean = headline.lstrip("-*•0123456789. \t")
            if headline_clean and headline_clean not in seen:
                unique_headlines.append(headline_clean)
                seen.add(headline_clean)

    numbered_headlines = [f"{i+1}. {hl}" for i, hl in enumerate(unique_headlines)]

    return "\n".join(numbered_headlines)
