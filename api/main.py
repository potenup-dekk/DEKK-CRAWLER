from fastapi import FastAPI

app = FastAPI(title="DEKK Crawler API")


@app.get("/health")
def health_check():
    return {"status": "ok"}
