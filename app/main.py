from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes_index import router as index_router
from app.api.routes_query import router as query_router
import os

app = FastAPI(
    title="CodeLens API",
    description="RAG-powered codebase Q&A system",
    version="1.0.0",
)

# In production lock this down to your Vercel frontend URL
# Set FRONTEND_URL environment variable on HF Spaces
FRONTEND_URL = os.environ.get("FRONTEND_URL", "*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL] if FRONTEND_URL != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(index_router)
app.include_router(query_router)

@app.get("/health")
def health():
    return {"status": "ok"}