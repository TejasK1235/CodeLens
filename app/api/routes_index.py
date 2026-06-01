import asyncio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.utils.cache import is_indexed, get_cache_status, make_repo_id
from app.utils.github import parse_github_url, get_repo_metadata, get_latest_commit_hash, validate_repo_size
from app.ingestion.cloner import clone_repo
from app.ingestion.parser import parse_repo
from app.ingestion.chunker import process_chunks
from app.indexing.embedder import embed_chunks
from app.indexing.store import save_chunks

router = APIRouter()

_job_status: dict[str, dict] = {}


class IndexRequest(BaseModel):
    github_url: str


def run_indexing_job(repo_id: str, github_url: str) -> None:
    try:
        _job_status[repo_id] = {
            "status": "cloning",
            "stage": "Cloning repository",
            "chunks_processed": 0,
            "chunks_total": 0,
        }

        clone_result = clone_repo(github_url)

        _job_status[repo_id].update({
            "status": "parsing",
            "stage": "Parsing files with tree-sitter",
        })

        raw_chunks = parse_repo(clone_result["clone_path"])

        _job_status[repo_id].update({
            "status": "chunking",
            "stage": "Processing and validating chunks",
        })

        final_chunks = process_chunks(raw_chunks, repo_id)

        _job_status[repo_id].update({
            "status": "embedding",
            "stage": "Embedding chunks",
            "chunks_total": len(final_chunks),
        })

        documents, embeddings = embed_chunks(final_chunks)

        _job_status[repo_id].update({
            "status": "storing",
            "stage": "Saving to ChromaDB",
            "chunks_processed": len(final_chunks),
        })

        save_chunks(repo_id, final_chunks, documents, embeddings)

        _job_status[repo_id] = {
            "status": "ready",
            "stage": "Indexing complete",
            "chunks_processed": len(final_chunks),
            "chunks_total": len(final_chunks),
            "clone_result": clone_result,
        }

    except Exception as e:
        _job_status[repo_id] = {
            "status": "error",
            "stage": f"Failed: {str(e)}",
            "chunks_processed": 0,
            "chunks_total": 0,
        }
        print(f"[IndexJob] Error for {repo_id}: {e}")


@router.post("/index")
async def index_repo(request: IndexRequest, background_tasks: BackgroundTasks):
    github_url = request.github_url.strip()

    try:
        owner, repo = parse_github_url(github_url)
        metadata = get_repo_metadata(owner, repo)
        validate_repo_size(metadata["size_kb"])
        commit_hash = get_latest_commit_hash(owner, repo, metadata["default_branch"])
        repo_id = make_repo_id(owner, repo, commit_hash)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if is_indexed(repo_id):
        cache = get_cache_status(repo_id)
        return {
            "repo_id": repo_id,
            "status": "cached",
            "message": "Repository already indexed. Ready to query.",
            "chunk_count": cache.get("chunk_count"),
            "full_name": metadata["full_name"],
            "commit_hash": commit_hash,
        }

    if repo_id in _job_status and _job_status[repo_id]["status"] not in ("error", "ready"):
        return {
            "repo_id": repo_id,
            "status": "indexing",
            "message": "Indexing already in progress.",
        }

    background_tasks.add_task(run_indexing_job, repo_id, github_url)
    _job_status[repo_id] = {
        "status": "queued",
        "stage": "Job queued",
        "chunks_processed": 0,
        "chunks_total": 0,
    }

    return {
        "repo_id": repo_id,
        "status": "indexing",
        "message": "Indexing started. Poll /index/status/{repo_id} for progress.",
        "full_name": metadata["full_name"],
        "commit_hash": commit_hash,
    }


@router.get("/index/status/{repo_id}")
async def index_status(repo_id: str):
    if is_indexed(repo_id):
        cache = get_cache_status(repo_id)
        return {
            "repo_id": repo_id,
            "status": "ready",
            "stage": "Indexing complete",
            "chunk_count": cache.get("chunk_count"),
            "full_name": cache.get("full_name"),
            "commit_hash": cache.get("commit_hash"),
        }

    if repo_id not in _job_status:
        raise HTTPException(
            status_code=404,
            detail=f"No indexing job found for repo_id: {repo_id}"
        )

    job = _job_status[repo_id]
    return {
        "repo_id": repo_id,
        "status": job["status"],
        "stage": job["stage"],
        "chunks_processed": job.get("chunks_processed", 0),
        "chunks_total": job.get("chunks_total", 0),
    }