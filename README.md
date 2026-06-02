# CodeLens

**Ask natural language questions about any GitHub codebase. Get accurate, source-cited answers grounded in the actual code.**

CodeLens is a RAG (Retrieval-Augmented Generation) system that indexes any public GitHub repository and lets you query it in plain English. It uses semantic chunking, cross-encoder reranking, HyDE query enrichment, and dependency-aware context expansion to return precise answers with direct links to the relevant lines in the source code.

---

## Features

- **AST-based semantic chunking** — tree-sitter parses Python and JavaScript into function/class boundaries rather than arbitrary line windows
- **HyDE query enrichment** — generates a hypothetical code answer before retrieval to bridge the vocabulary gap between natural language questions and code tokens
- **CrossEncoder reranking** — two-stage retrieval: bi-encoder for recall, cross-encoder for precision
- **Dependency expansion** — follows the call graph of retrieved functions to surface dependent context automatically
- **File summary chunks** — one LLM-generated description per file enables architectural queries like "what handles authentication?"
- **Line-level GitHub citations** — every source links to the exact line in the exact commit that was indexed
- **Comment stripping** — dead code and TODO comments excluded from embeddings
- **Zero API cost** — local sentence-transformers embeddings, Groq free tier LLM, local ChromaDB
- **Auth + conversation history** — Supabase handles login/signup and persists all conversations

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.11+ |
| Parsing | tree-sitter (Python, JavaScript, TypeScript) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (local, no API) |
| Reranking | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Vector DB | ChromaDB (PersistentClient, cosine space) |
| RAG chain | LangChain LCEL |
| LLM | Groq `llama-3.1-8b-instant` (query + HyDE) |
| Frontend | React + Vite |
| HTTP client | axios |
| Auth + DB | Supabase (Postgres + Auth) |

---

## Architecture

```
User query
    │
    ▼
HyDE: generate hypothetical answer (Groq)
    │
    ▼
Embed enriched query (sentence-transformers)
    │
    ▼
ChromaDB cosine search → top 8 chunks
    │
    ▼
CrossEncoder rerank → top 4
    │
    ▼
Dependency expansion → fetch called functions (≤2)
    │
    ▼
LangChain LCEL: context + history → Groq → answer
    │
    ▼
Response with sources (GitHub line URLs)
```

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Groq API key — free at [console.groq.com](https://console.groq.com)
- Supabase project — free at [supabase.com](https://supabase.com)

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env in project root
echo "GROQ_API_KEY=your_groq_key_here" > .env

# Start backend
uvicorn app.main:app --reload
# Runs at http://localhost:8000
# API docs at http://localhost:8000/docs
```

On first run, sentence-transformers downloads `all-MiniLM-L6-v2` (~90MB) and the cross-encoder (~85MB). Both are cached locally after first download.

### Supabase Setup

In your Supabase project's SQL Editor, create the three required tables:

```sql
create table indexed_repos (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users not null,
  repo_id text not null,
  full_name text not null,
  github_url text not null,
  commit_hash text not null,
  chunk_count int default 0,
  indexed_at timestamptz default now(),
  last_queried_at timestamptz default now(),
  unique(user_id, repo_id)
);

create table conversations (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references auth.users not null,
  repo_id text not null,
  repo_full_name text not null,
  title text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table messages (
  id uuid default gen_random_uuid() primary key,
  conversation_id uuid references conversations on delete cascade not null,
  user_id uuid references auth.users not null,
  role text not null,
  content text not null,
  sources jsonb default '[]',
  stats jsonb default null,
  created_at timestamptz default now()
);

alter table indexed_repos enable row level security;
alter table conversations enable row level security;
alter table messages enable row level security;

create policy "users see own repos" on indexed_repos for all using (auth.uid() = user_id);
create policy "users see own conversations" on conversations for all using (auth.uid() = user_id);
create policy "users see own messages" on messages for all using (auth.uid() = user_id);
```

In **Authentication → Sign In / Providers → Email**, disable "Confirm email" for local development.

### Frontend

```bash
cd frontend
npm install

# Create frontend/.env
# IMPORTANT: Use base URL only — no /rest/v1 suffix
VITE_SUPABASE_URL=https://yourproject.supabase.co
VITE_SUPABASE_ANON_KEY=eyJ...
VITE_API_URL=http://localhost:8000

npm run dev
# Runs at http://localhost:5173
```

---

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/index` | POST | Start indexing a GitHub repo. Body: `{"github_url": "..."}` |
| `/index/status/{repo_id}` | GET | Poll indexing progress. Returns stage + chunk counts. |
| `/query` | POST | Query an indexed repo. Body: `{"repo_id", "query", "conversation_history"}` |
| `/health` | GET | Health check |

### POST /index response

```json
{
  "repo_id": "abc123def456",
  "status": "indexing",
  "full_name": "owner/repo",
  "commit_hash": "a1b2c3d4e5f6",
  "message": "Indexing started. Poll /index/status/{repo_id} for progress."
}
```

If the repo at that commit is already indexed, `status` is `"cached"` and the response is immediate.

### POST /query response

```json
{
  "repo_id": "abc123def456",
  "query": "how does authentication work?",
  "answer": "Authentication is handled in auth.py by the verify_token function...",
  "sources": [
    {
      "name": "verify_token",
      "file_path": "auth/auth.py",
      "start_line": 45,
      "end_line": 72,
      "similarity": 0.8234,
      "is_expanded": false,
      "github_url": "https://github.com/owner/repo/blob/a1b2c3.../auth/auth.py#L45"
    }
  ],
  "retrieved_count": 4,
  "expanded_count": 1
}
```

---

## Configuration

All constants are in `app/config.py`. Change values here and nowhere else.

| Constant | Default | Notes |
|---|---|---|
| `GROQ_MODEL_QUERY` | `llama-3.1-8b-instant` | Used for Q&A and HyDE generation |
| `GROQ_MODEL_COMPLEX` | `llama-3.3-70b-versatile` | Available for complex queries |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Local, no API cost |
| `MAX_REPO_SIZE_KB` | `204800` | 200MB limit |
| `MAX_CHUNK_TOKENS` | `512` | Oversized chunks are split |
| `MIN_CHUNK_WORDS` | `5` | Undersized chunks are dropped |
| `TOP_K_RETRIEVAL` | `8` | Candidates before reranking |
| `SIMILARITY_THRESHOLD` | `0.3` | Cosine similarity floor |

---

## Supported Languages

| Language | Chunking Strategy |
|---|---|
| Python (`.py`) | tree-sitter AST — function/class boundaries |
| JavaScript (`.js`) | tree-sitter AST — function/arrow/class/method |
| TypeScript (`.ts`) | tree-sitter AST (requires tree-sitter-typescript) |
| Markdown (`.md`) | Heading-level sections |
| Jupyter Notebooks (`.ipynb`) | Per markdown cell + combined code cells |
| Java, C++, C# | 40-line fixed blocks |

---

## Project Structure

```
codelens/
├── app/
│   ├── main.py              # FastAPI app, CORS, routers
│   ├── config.py            # All constants — edit here only
│   ├── api/
│   │   ├── routes_index.py  # POST /index, GET /index/status
│   │   └── routes_query.py  # POST /query
│   ├── ingestion/
│   │   ├── cloner.py        # Git clone, GitHub API
│   │   ├── parser.py        # tree-sitter + format-specific parsers
│   │   └── chunker.py       # Size enforcement, IDs, file summaries
│   ├── indexing/
│   │   ├── embedder.py      # sentence-transformers singleton
│   │   └── store.py         # ChromaDB CRUD
│   ├── retrieval/
│   │   ├── retriever.py     # Semantic search + CrossEncoder rerank
│   │   └── expander.py      # Dependency expansion + full pipeline
│   ├── generation/
│   │   ├── prompts.py       # System prompt, context formatter
│   │   └── chain.py         # HyDE, LangChain chain, run_query
│   └── utils/
│       ├── cache.py         # repo_id hashing, registry.json
│       └── github.py        # GitHub REST API helpers
├── storage/
│   ├── repos/               # Cloned repos (gitignored)
│   └── chroma/              # ChromaDB collections (gitignored)
└── frontend/
    └── src/
        ├── App.jsx          # Auth state machine
        ├── supabase.js      # Supabase client + DB helpers
        ├── pages/
        │   ├── AuthPage.jsx
        │   └── Dashboard.jsx
        └── components/
            ├── RepoInput.jsx
            ├── IndexingProgress.jsx
            ├── ChatInterface.jsx
            └── SourcesPanel.jsx
```

---

## Key Design Decisions

**Why HyDE?** Natural language queries use different vocabulary than code. "How does auth work?" vs. `jwt_verify`, `decode_token`, `check_session`. HyDE generates a hypothetical code answer that introduces correct vocabulary into the embedding query.

**Why two-stage retrieval?** Bi-encoder cosine similarity is fast but approximate. Cross-encoder reranking is slow but precise. Retrieving 8 candidates with the bi-encoder and reranking to 4 with the cross-encoder gives best precision within the Groq token budget.

**Why dependency expansion?** A function's behavior often depends on functions it calls. Standard RAG retrieves only the most similar chunks. CodeLens additionally fetches called functions, giving the LLM the full dependency context it needs.

**Why local embeddings?** OpenAI embeddings cost money per token. `all-MiniLM-L6-v2` runs on CPU at ~500 chunks/second with excellent semantic similarity quality at zero cost.

**Why comment stripping?** Outdated comments pollute the embedding space. A deleted function that remains as a comment would surface as a top result for queries about it.

---

## Known Limitations

- **Groq free tier** (6000 TPM): approximately 2 concurrent users before rate limiting
- **ChromaDB ephemeral on Render free tier**: disk wiped on restart — use persistent storage in production
- **Dependency expansion depth**: one level only; multi-hop call chains are not fully surfaced
- **No private repo support**: requires unauthenticated GitHub access
- **Java/C++/C# chunking**: 40-line fixed blocks, not AST-based

---

## License

MIT