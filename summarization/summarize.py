# summarization\summarize.py
import nltk
from summarization.model import get_summarization_model

try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt")


def extractive_summarize(text: str, num_sentences: int = 2) -> str:
    from nltk.tokenize import sent_tokenize

    sentences = sent_tokenize(text)
    return " ".join(sentences[:num_sentences])


def abstractive_summarize(text: str, max_length: int = 64) -> str:
    model, tokenizer = get_summarization_model()

    inputs = tokenizer([text], max_length=512, truncation=True, return_tensors="pt")

    summary_ids = model.generate(
        inputs["input_ids"],
        max_length=max_length,
        min_length=10,
        length_penalty=1.2,
        num_beams=4,
        early_stopping=True,
    )

    return tokenizer.decode(summary_ids[0], skip_special_tokens=True).strip()
