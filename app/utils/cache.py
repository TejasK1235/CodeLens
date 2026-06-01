import hashlib
import os
import json
from app.config import REPOS_DIR, CHROMA_DIR
from app.indexing.store import collection_exists, get_collection_stats


CACHE_REGISTRY_PATH = os.path.join(CHROMA_DIR, "registry.json")


def make_repo_id(owner: str, repo: str, commit_hash: str) -> str:
    raw = f"{owner}/{repo}@{commit_hash}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def load_registry() -> dict:
    if not os.path.exists(CACHE_REGISTRY_PATH):
        return {}
    try:
        with open(CACHE_REGISTRY_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_registry(registry: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_REGISTRY_PATH), exist_ok=True)
    with open(CACHE_REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2)


def register_repo(repo_id: str, metadata: dict, commit_hash: str) -> None:
    registry = load_registry()
    registry[repo_id] = {
        "repo_id": repo_id,
        "full_name": metadata["full_name"],
        "owner": metadata["owner"],
        "repo": metadata["repo"],
        "commit_hash": commit_hash,
        "size_kb": metadata["size_kb"],
        "description": metadata.get("description", ""),
        "clone_path": os.path.join(REPOS_DIR, repo_id),
    }
    save_registry(registry)


def get_repo_info(repo_id: str) -> dict | None:
    registry = load_registry()
    return registry.get(repo_id)


def is_indexed(repo_id: str) -> bool:
    return collection_exists(repo_id)


def get_cache_status(repo_id: str) -> dict:
    info = get_repo_info(repo_id)
    indexed = is_indexed(repo_id)

    if not info or not indexed:
        return {
            "repo_id": repo_id,
            "status": "not_found",
            "indexed": False,
        }

    stats = get_collection_stats(repo_id)
    return {
        "repo_id": repo_id,
        "status": "ready",
        "indexed": True,
        "full_name": info["full_name"],
        "commit_hash": info["commit_hash"],
        "chunk_count": stats["chunk_count"],
        "clone_path": info["clone_path"],
        "owner": info["owner"],
        "repo": info["repo"],
    }