import os
import json
import chromadb
from app.config import CHROMA_DIR


def get_client() -> chromadb.PersistentClient:
    os.makedirs(CHROMA_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DIR)


def collection_exists(repo_id: str) -> bool:
    client = get_client()
    existing = [c.name for c in client.list_collections()]
    return repo_id in existing


def get_collection(repo_id: str):
    client = get_client()
    return client.get_collection(name=repo_id)


def create_collection(repo_id: str):
    client = get_client()
    return client.create_collection(
        name=repo_id,
        metadata={"hnsw:space": "cosine"},
    )


# def delete_collection(repo_id: str) -> bool:
#     client = get_client()
#     existing = [c.name for c in client.list_collections()]
#     if repo_id in existing:
#         client.delete_collection(name=repo_id)
#         print(f"[Store] Deleted collection: {repo_id}")
#         return True
#     return False


def save_chunks(repo_id: str, chunks: list[dict], documents: list[str], embeddings: list[list[float]]) -> int:
    collection = create_collection(repo_id)

    ids = [c["chunk_id"] for c in chunks]

    metadatas = []
    for c in chunks:
        metadatas.append({
            "name": c["name"],
            "type": c["type"],
            "file_path": c["file_path"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "language": c["language"],
            "calls": json.dumps(c["calls"]),
            "repo_id": c["repo_id"],
        })

    batch_size = 100
    total = len(chunks)

    for i in range(0, total, batch_size):
        batch_end = min(i + batch_size, total)
        collection.add(
            ids=ids[i:batch_end],
            documents=documents[i:batch_end],
            embeddings=embeddings[i:batch_end],
            metadatas=metadatas[i:batch_end],
        )
        print(f"[Store] Saved batch {i}–{batch_end} of {total}")

    print(f"[Store] All {total} chunks saved to collection: {repo_id}")
    return total


def query_collection(repo_id: str, query_embedding: list[float], top_k: int) -> dict:
    collection = get_collection(repo_id)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    return results


def fetch_chunks_by_names(repo_id: str, function_names: list[str]) -> list[dict]:
    if not function_names:
        return []
    collection = get_collection(repo_id)
    results = collection.get(
        where={"name": {"$in": function_names}},
        include=["documents", "metadatas"],
    )
    items = []
    for i in range(len(results["ids"])):
        items.append({
            "chunk_id": results["ids"][i],
            "document": results["documents"][i],
            "metadata": results["metadatas"][i],
        })
    return items


def get_collection_stats(repo_id: str) -> dict:
    collection = get_collection(repo_id)
    count = collection.count()
    return {
        "repo_id": repo_id,
        "chunk_count": count,
    }


def delete_collection(repo_id: str) -> bool:
    """Delete a ChromaDB collection entirely."""
    try:
        client = get_client()
        client.delete_collection(name=repo_id)
        print(f"[Store] Deleted collection: {repo_id}")
        return True
    except Exception as e:
        print(f"[Store] Failed to delete collection {repo_id}: {e}")
        return False