from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.utils.cache import is_indexed, get_cache_status
from app.generation.chain import run_query

router = APIRouter()

class ConversationTurn(BaseModel):
    query: str
    answer: str

class QueryRequest(BaseModel):
    repo_id: str
    query: str
    conversation_history: list[ConversationTurn] = []
    grievous_mode: bool = False  # Easter egg flag

@router.post("/query")
async def query_repo(request: QueryRequest):
    if not is_indexed(request.repo_id):
        raise HTTPException(
            status_code=404,
            detail=f"Repository {request.repo_id} is not indexed. Please index it first."
        )

    cache = get_cache_status(request.repo_id)
    if not cache:
        raise HTTPException(status_code=404, detail="Repository metadata not found.")

    clone_result = {
        "owner": cache.get("owner", ""),
        "repo":  cache.get("repo", ""),
        "commit_hash": cache.get("commit_hash", ""),
        "full_name": cache.get("full_name", ""),
    }

    history = [
        {"query": turn.query, "answer": turn.answer}
        for turn in request.conversation_history
    ]

    result = run_query(
        repo_id=request.repo_id,
        query=request.query,
        clone_result=clone_result,
        conversation_history=history,
        grievous_mode=request.grievous_mode,
    )

    return {
        "repo_id": request.repo_id,
        "query": request.query,
        "answer": result["answer"],
        "sources": result["sources"],
        "retrieved_count": result["retrieved_count"],
        "expanded_count": result["expanded_count"],
    }