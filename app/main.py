from fastapi import FastAPI

app = FastAPI(title="TinyFlags Backend")


@app.get("/health")
async def health():
    return {"status": "ok"}
