from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL
from app.ingestion.chunker import build_chunk_document

_model = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"[Embedder] Loading model: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        print(f"[Embedder] Model loaded")
    return _model


def embed_chunks(chunks: list[dict]) -> tuple[list[str], list[list[float]]]:
    model = get_model()

    documents = [build_chunk_document(c) for c in chunks]

    print(f"[Embedder] Embedding {len(documents)} chunks...")
    embeddings = model.encode(
        documents,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    print(f"[Embedder] Done. Embedding shape: {embeddings.shape}")
    return documents, embeddings.tolist()


def embed_query(query: str) -> list[float]:
    model = get_model()
    embedding = model.encode(query, convert_to_numpy=True)
    return embedding.tolist()