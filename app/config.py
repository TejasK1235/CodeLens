import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# print(GROQ_API_KEY)

GROQ_MODEL_QUERY = "llama-3.1-8b-instant"
GROQ_MODEL_COMPLEX = "llama-3.3-70b-versatile"

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

STORAGE_DIR = "storage"
REPOS_DIR = f"{STORAGE_DIR}/repos"
CHROMA_DIR = f"{STORAGE_DIR}/chroma"

MAX_REPO_SIZE_KB = 204800
MAX_CHUNK_TOKENS = 512
MIN_CHUNK_WORDS = 5

SUPPORTED_EXTENSIONS = {".py", ".js", ".md", ".ts", ".java", ".cpp", ".cs", ".ipynb"}

TOP_K_RETRIEVAL = 8
SIMILARITY_THRESHOLD = 0.3