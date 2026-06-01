import requests
from app.config import MAX_REPO_SIZE_KB


def parse_github_url(url: str) -> tuple[str, str]:
    url = url.rstrip("/").replace(".git", "")
    parts = url.split("github.com/")
    if len(parts) != 2:
        raise ValueError(f"Invalid GitHub URL: {url}")
    segments = parts[1].split("/")
    if len(segments) < 2:
        raise ValueError(f"Could not parse owner/repo from URL: {url}")
    return segments[0], segments[1]


def get_repo_metadata(owner: str, repo: str) -> dict:
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    response = requests.get(api_url, timeout=10)
    if response.status_code == 404:
        raise ValueError(f"Repo not found or is private: {owner}/{repo}")
    if response.status_code != 200:
        raise RuntimeError(f"GitHub API error: {response.status_code}")
    data = response.json()
    return {
        "owner": owner,
        "repo": repo,
        "full_name": data["full_name"],
        "size_kb": data["size"],
        "default_branch": data["default_branch"],
        "description": data.get("description", ""),
    }


def get_latest_commit_hash(owner: str, repo: str, branch: str) -> str:
    api_url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"
    response = requests.get(api_url, timeout=10)
    if response.status_code != 200:
        raise RuntimeError(f"Could not fetch commit hash: {response.status_code}")
    return response.json()["sha"][:12]


def validate_repo_size(size_kb: int) -> None:
    if size_kb > MAX_REPO_SIZE_KB:
        raise ValueError(
            f"Repo too large: {size_kb} KB. "
            f"Limit is {MAX_REPO_SIZE_KB} KB ({MAX_REPO_SIZE_KB // 1024} MB)."
        )