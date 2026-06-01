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


@router.post("/query")
async def query_repo(request: QueryRequest):
    if not is_indexed(request.repo_id):
        raise HTTPException(
            status_code=404,
            detail=f"No indexed repository found for repo_id: {request.repo_id}. Run /index first."
        )

    cache = get_cache_status(request.repo_id)
    if cache["status"] != "ready":
        raise HTTPException(
            status_code=400,
            detail="Repository is not ready. Indexing may still be in progress."
        )

    clone_result = {
        "owner": cache["owner"],
        "repo": cache["repo"],
        "full_name": cache["full_name"],
        "commit_hash": cache["commit_hash"],
    }

    history = [
        {"query": turn.query, "answer": turn.answer}
        for turn in request.conversation_history
    ]

    try:
        result = run_query(
            repo_id=request.repo_id,
            query=request.query,
            clone_result=clone_result,
            conversation_history=history,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    return {
        "repo_id": request.repo_id,
        "query": request.query,
        "answer": result["answer"],
        "sources": result["sources"],
        "retrieved_count": result["retrieved_count"],
        "expanded_count": result["expanded_count"],
    }