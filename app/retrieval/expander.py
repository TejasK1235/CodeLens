import json
from app.indexing.store import fetch_chunks_by_names


SKIP_CALLS = {
    "print", "len", "range", "int", "str", "float", "bool", "list",
    "dict", "set", "tuple", "type", "isinstance", "issubclass",
    "getattr", "setattr", "hasattr", "callable", "iter", "next",
    "open", "super", "reversed", "enumerate", "zip", "map", "filter",
    "sorted", "min", "max", "sum", "abs", "round", "repr", "hash",
    "id", "dir", "vars", "locals", "globals", "TypeError", "ValueError",
    "RuntimeError", "KeyError", "IndexError", "AttributeError",
    "Exception", "NotImplementedError", "StopIteration", "bool",
}


def clean_call_name(call: str) -> str:
    if "." in call:
        parts = call.split(".")
        return parts[-1]
    return call


def extract_expansion_targets(retrieved_chunks: list[dict]) -> list[str]:
    targets = set()
    for chunk in retrieved_chunks:
        for call in chunk.get("calls", []):
            clean = clean_call_name(call)
            if clean and clean not in SKIP_CALLS and len(clean) > 2:
                targets.add(clean)
    return list(targets)


def expand(repo_id: str, retrieved_chunks: list[dict]) -> list[dict]:
    already_retrieved_ids = {c["chunk_id"] for c in retrieved_chunks}

    targets = extract_expansion_targets(retrieved_chunks)
    if not targets:
        print(f"[Expander] No expansion targets found")
        return []

    print(f"[Expander] Looking up {len(targets)} referenced functions...")
    raw_expanded = fetch_chunks_by_names(repo_id, targets)

    expanded = []
    for item in raw_expanded:
        if item["chunk_id"] in already_retrieved_ids:
            continue

        metadata = item["metadata"]
        calls = []
        try:
            calls = json.loads(metadata.get("calls", "[]"))
        except Exception:
            pass

        expanded.append({
            "chunk_id": item["chunk_id"],
            "document": item["document"],
            "similarity": None,
            "name": metadata["name"],
            "type": metadata["type"],
            "file_path": metadata["file_path"],
            "start_line": metadata["start_line"],
            "end_line": metadata["end_line"],
            "language": metadata["language"],
            "calls": calls,
            "repo_id": metadata["repo_id"],
            "is_expanded": True,
        })

    print(f"[Expander] Added {len(expanded)} expanded chunks")
    return expanded



from app.retrieval.retriever import retrieve, rerank


def retrieve_with_expansion(repo_id: str, query: str, max_hops: int = 2) -> dict:
    retrieved = retrieve(repo_id, query)
    reranked = rerank(query, retrieved, top_k=4)
    
    all_chunks = list(reranked)
    seen_ids = {c["chunk_id"] for c in all_chunks}
    frontier = reranked  # start expansion from reranked chunks
    
    for hop in range(max_hops):
        expanded = expand(repo_id, frontier)
        new_chunks = [c for c in expanded if c["chunk_id"] not in seen_ids]
        if not new_chunks:
            break
        # cap new chunks per hop to control token budget
        new_chunks = new_chunks[:2]
        all_chunks.extend(new_chunks)
        seen_ids.update(c["chunk_id"] for c in new_chunks)
        frontier = new_chunks  # next hop expands from what we just found
    
    return {
        "retrieved_count": len(reranked),
        "expanded_count": len(all_chunks) - len(reranked),
        "chunks": all_chunks,
    }