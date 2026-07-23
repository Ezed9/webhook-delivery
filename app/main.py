from fastapi import FastAPI

app = FastAPI(title="webhook-delivery")

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
    