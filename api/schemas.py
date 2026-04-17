from typing import Literal, Optional

from pydantic import BaseModel


class ExtractionResult(BaseModel):
    url: str
    productName: Optional[str] = None
    brandName: Optional[str] = None
    imageUrl: Optional[str] = None
    extracted_via: Optional[Literal["static", "playwright", "error"]] = None


class ErrorResponse(BaseModel):
    error: str
    detail: str
