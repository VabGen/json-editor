# state.py
from pydantic import BaseModel
from typing import TypedDict, Optional, Dict, Any


class SummarizationRequest(BaseModel):
    text: Optional[str] = None
    summarization_type: str = "extractive"  # "abstractive" или "extractive"


class AgentState(TypedDict):
    json_: Dict[str, Any]
    instruction: str
    json_schema: Optional[Dict[str, Any]]
    pdf_text: Optional[str]
    summarization_type: Optional[str]
    summary: Optional[str]
    updated_json_str: Optional[str]
    final_json: Optional[Dict[str, Any]]
    error: Optional[str]

    # class Config:
    #     arbitrary_types_allowed = True
