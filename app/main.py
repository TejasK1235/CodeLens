from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes_index import router as index_router
from app.api.routes_query import router as query_router

app = FastAPI(
    title="CodeLens",
    description="RAG-powered codebase question answering system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(index_router, tags=["indexing"])
app.include_router(query_router, tags=["query"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "CodeLens"}