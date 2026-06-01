import json
from app.indexing.embedder import embed_query
from app.indexing.store import query_collection, collection_exists
from app.config import TOP_K_RETRIEVAL, SIMILARITY_THRESHOLD


def format_results(raw_results: dict) -> list[dict]:
    formatted = []
    ids = raw_results["ids"][0]
    documents = raw_results["documents"][0]
    metadatas = raw_results["metadatas"][0]
    distances = raw_results["distances"][0]

    for i in range(len(ids)):
        distance = distances[i]
        similarity = 1 - distance

        if similarity < SIMILARITY_THRESHOLD:
            continue

        metadata = metadatas[i]
        calls = []
        try:
            calls = json.loads(metadata.get("calls", "[]"))
        except Exception:
            pass

        formatted.append({
            "chunk_id": ids[i],
            "document": documents[i],
            "similarity": round(similarity, 4),
            "name": metadata["name"],
            "type": metadata["type"],
            "file_path": metadata["file_path"],
            "start_line": metadata["start_line"],
            "end_line": metadata["end_line"],
            "language": metadata["language"],
            "calls": calls,
            "repo_id": metadata["repo_id"],
        })

    return formatted


def retrieve(repo_id: str, query: str, top_k: int = TOP_K_RETRIEVAL) -> list[dict]:
    if not collection_exists(repo_id):
        raise ValueError(f"No indexed collection found for repo: {repo_id}")

    print(f"[Retriever] Embedding query...")
    query_embedding = embed_query(query)

    print(f"[Retriever] Searching top {top_k} chunks...")
    raw_results = query_collection(repo_id, query_embedding, top_k)

    results = format_results(raw_results)
    print(f"[Retriever] {len(results)} results above similarity threshold")
    return results

from sentence_transformers import CrossEncoder

_reranker = None

def get_reranker():
    global _reranker
    if _reranker is None:
        print("[Reranker] Loading cross-encoder model...")
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        print("[Reranker] Loaded")
    return _reranker

def rerank(query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
    if not chunks:
        return chunks
    reranker = get_reranker()
    pairs = [[query, c["document"]] for c in chunks]
    scores = reranker.predict(pairs)
    scored = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    reranked = []
    for score, chunk in scored[:top_k]:
        chunk["rerank_score"] = round(float(score), 4)
        reranked.append(chunk)
    print(f"[Reranker] Reranked {len(chunks)} → {len(reranked)} chunks")
    return reranked