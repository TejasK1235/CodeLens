import os
import shutil
import git
from app.config import REPOS_DIR
from app.utils.github import (
    parse_github_url,
    get_repo_metadata,
    get_latest_commit_hash,
    validate_repo_size,
)
from app.utils.cache import make_repo_id, register_repo


def make_clone_path(repo_id: str) -> str:
    return os.path.join(REPOS_DIR, repo_id)


def clone_repo(github_url: str) -> dict:
    print(f"[Cloner] Parsing URL: {github_url}")
    owner, repo = parse_github_url(github_url)

    print(f"[Cloner] Fetching metadata for {owner}/{repo}...")
    metadata = get_repo_metadata(owner, repo)
    validate_repo_size(metadata["size_kb"])
    print(f"[Cloner] Repo size: {metadata['size_kb']} KB — within limit")

    commit_hash = get_latest_commit_hash(owner, repo, metadata["default_branch"])
    print(f"[Cloner] Latest commit: {commit_hash}")

    repo_id = make_repo_id(owner, repo, commit_hash)
    clone_path = make_clone_path(repo_id)

    if os.path.exists(clone_path):
        print(f"[Cloner] Already cloned at {clone_path} — skipping")
        return {
            "repo_id": repo_id,
            "clone_path": clone_path,
            "commit_hash": commit_hash,
            "already_existed": True,
            **metadata,
        }

    os.makedirs(REPOS_DIR, exist_ok=True)
    print(f"[Cloner] Cloning into {clone_path}...")
    git.Repo.clone_from(github_url, clone_path, depth=1)
    print(f"[Cloner] Clone complete")

    result = {
        "repo_id": repo_id,
        "clone_path": clone_path,
        "commit_hash": commit_hash,
        "already_existed": False,
        **metadata,
    }

    register_repo(repo_id, metadata, commit_hash)
    return result


def delete_clone(repo_id: str) -> bool:
    clone_path = make_clone_path(repo_id)
    if os.path.exists(clone_path):
        shutil.rmtree(clone_path)
        print(f"[Cloner] Deleted clone at {clone_path}")
        return True
    return False