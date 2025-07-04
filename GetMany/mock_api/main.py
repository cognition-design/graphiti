from fastapi import FastAPI
from api.endpoints import router as api_router

app = FastAPI(
    title="Getmany Mock Service API",
    description="This is a mock API for the Getmany Service for n8n workflow development.",
    version="1.0.0"
)

app.include_router(api_router, prefix="/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)


