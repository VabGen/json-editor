# summarization\model.py
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch

MODEL_NAME = "csebuetnlp/mT5_multilingual_XLSum"  # русский!
# "facebook/bart-base"  # английский!

_model, _tokenizer = None, None


def get_summarization_model():
    global _model, _tokenizer
    if _model is None:
        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForSeq2SeqLM.from_pretrained(
            MODEL_NAME, torch_dtype=torch.float32
        )
    return _model, _tokenizer
