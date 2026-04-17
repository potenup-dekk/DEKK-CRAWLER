from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.extractor import InvalidURLError, SSRFBlockedError, extract_static, validate_and_guard
from api.schemas import ExtractionResult

app = FastAPI(title="DEKK Crawler API")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"error": "INVALID_URL", "detail": "유효하지 않은 URL 형식입니다"},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/extract", response_model=ExtractionResult)
def extract(url: str):
    try:
        validate_and_guard(url)
    except (InvalidURLError, SSRFBlockedError) as e:
        return JSONResponse(
            status_code=400,
            content={"error": "INVALID_URL", "detail": str(e)},
        )

    result = extract_static(url)

    if "error" in result and "detail" in result:
        return JSONResponse(
            status_code=400,
            content=result,
        )

    return ExtractionResult(url=url, **result)
