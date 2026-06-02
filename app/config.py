import os
from pathlib import Path

# ── LLM Models ────────────────────────────────────────────────────────────────
GROQ_MODEL_QUERY   = "llama-3.1-8b-instant"
GROQ_MODEL_COMPLEX = "llama-3.3-70b-versatile"

# ── Embedding ─────────────────────────────────────────────────────────────────
EMBEDDING_MODEL  = "sentence-transformers/all-MiniLM-L6-v2"
RERANKER_MODEL   = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# ── Storage paths — use /data on HF Spaces (persistent), local fallback ───────
_IS_HF_SPACES = os.path.exists("/data")
_BASE_STORAGE = Path("/data") if _IS_HF_SPACES else Path("storage")

CHROMA_DIR = str(_BASE_STORAGE / "chroma")
REPOS_DIR  = str(_BASE_STORAGE / "repos")

# Ensure directories exist at import time
Path(CHROMA_DIR).mkdir(parents=True, exist_ok=True)
Path(REPOS_DIR).mkdir(parents=True, exist_ok=True)

# ── Chunking ──────────────────────────────────────────────────────────────────
MAX_CHUNK_TOKENS = 512
MIN_CHUNK_WORDS  = 5
MAX_CHUNK_CHARS  = 800   # used in chain.py for LLM context budget

# ── Retrieval ─────────────────────────────────────────────────────────────────
TOP_K_RETRIEVAL      = 8
TOP_K_RERANK         = 4
SIMILARITY_THRESHOLD = 0.3

# ── Ingestion ─────────────────────────────────────────────────────────────────
MAX_REPO_SIZE_KB = 204800   # 200 MB
SUPPORTED_EXTENSIONS = {".py", ".js", ".ts", ".md", ".java", ".cpp", ".cs", ".ipynb"}

# ── API keys (always from environment — never hardcoded) ──────────────────────
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")   