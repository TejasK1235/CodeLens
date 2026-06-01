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


# def retrieve_with_expansion(repo_id: str, query: str) -> dict:
#     from app.retrieval.retriever import retrieve

#     retrieved = retrieve(repo_id, query)

#     expanded = expand(repo_id, retrieved)

#     for chunk in retrieved:
#         chunk["is_expanded"] = False

#     all_chunks = retrieved + expanded

#     return {
#         "query": query,
#         "retrieved_count": len(retrieved),
#         "expanded_count": len(expanded),
#         "total_chunks": len(all_chunks),
#         "chunks": all_chunks,
#     }

from app.retrieval.retriever import retrieve, rerank


def retrieve_with_expansion(repo_id: str, query: str) -> dict:
    # Step 1: retrieve semantically
    retrieved = retrieve(repo_id, query)
    
    # Step 2: rerank only the retrieved chunks (not expanded)
    reranked = rerank(query, retrieved, top_k=4)
    
    # Step 3: expand from the reranked results only
    expanded = expand(repo_id, reranked)
    
    # Step 4: cap expanded at 2, keep all reranked
    expanded = expanded[:2]
    
    for chunk in reranked:
        chunk["is_expanded"] = False

    all_chunks = reranked + expanded

    return {
        "query": query,
        "retrieved_count": len(reranked),
        "expanded_count": len(expanded),
        "total_chunks": len(all_chunks),
        "chunks": all_chunks,
    }