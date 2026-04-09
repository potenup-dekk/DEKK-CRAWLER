from typing import Optional, Literal
from pydantic import BaseModel


class ExtractionResult(BaseModel):
    url: str
    title: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    extracted_via: Optional[Literal["static", "playwright", "error"]] = None


class ErrorResponse(BaseModel):
    error: str
    detail: str
