from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from app.config import GROQ_API_KEY, GROQ_MODEL_QUERY
from app.generation.prompts import (
    build_qa_prompt,
    format_context,
    format_conversation_history,
)
from app.retrieval.expander import retrieve_with_expansion


def generate_hypothetical_answer(query: str) -> str:
    from langchain_groq import ChatGroq
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

   
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL_QUERY,
        temperature=0.5,
        max_tokens=150,
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", 
         "You are an expert software engineer. Given a question about a codebase, "
         "write a short hypothetical answer (3-5 sentences) that includes specific "
         "technical terms, function names, variable names, and module names that "
         "would likely appear in real code answering this question. "
         "Do not say you don't know. Write as if you have seen the code. "
         "Be specific and technical. Use programming vocabulary heavily."
        ),
        ("human", "Question: {query}\n\nWrite a hypothetical technical answer:"),
    ])

    chain = prompt | llm | StrOutputParser()
    hypothetical = chain.invoke({"query": query})
    print(f"[HyDE] Hypothetical answer generated ({len(hypothetical)} chars)")
    return hypothetical

# def build_chain():
#     llm = ChatGroq(
#         api_key=GROQ_API_KEY,
#         model=GROQ_MODEL_QUERY,
#         temperature=0.1,
#     )
#     prompt = build_qa_prompt()
#     parser = StrOutputParser()
#     return prompt | llm | parser

def build_chain():
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL_QUERY,
        temperature=0.1,
        max_tokens=1024,
        stop_sequences=["Note that", "However, the emphasis flag is not"],
    )
    prompt = build_qa_prompt()
    parser = StrOutputParser()
    return prompt | llm | parser


def build_github_url(clone_result: dict, file_path: str, start_line: int) -> str:
    owner = clone_result.get("owner", "")
    repo = clone_result.get("repo", "")
    commit = clone_result.get("commit_hash", "")
    clean_path = file_path.replace("\\", "/")
    return (
        f"https://github.com/{owner}/{repo}/blob/"
        f"{commit}/{clean_path}#L{start_line}"
    )


def format_sources(chunks: list[dict], clone_result: dict) -> list[dict]:
    sources = []
    seen = set()
    for chunk in chunks:
        key = chunk["chunk_id"]
        if key in seen:
            continue
        seen.add(key)
        github_url = build_github_url(
            clone_result,
            chunk["file_path"],
            chunk["start_line"],
        )
        sources.append({
            "name": chunk["name"],
            "file_path": chunk["file_path"],
            "start_line": chunk["start_line"],
            "end_line": chunk["end_line"],
            "similarity": chunk.get("similarity"),
            "is_expanded": chunk.get("is_expanded", False),
            "github_url": github_url,
        })
    return sources


MAX_CHUNKS_TO_LLM = 8
MAX_CHUNK_CHARS = 800


def truncate_chunk_text(document: str, max_chars: int) -> str:
    if len(document) <= max_chars:
        return document
    return document[:max_chars] + "\n... [truncated]"

def is_answer_grounded(answer: str, chunks: list[dict], threshold: float = 0.25) -> bool:
    from app.indexing.embedder import embed_query
    import numpy as np

    answer_embedding = embed_query(answer[:500])
    chunk_texts = [c["document"][:300] for c in chunks]
    if not chunk_texts:
        return False
    chunk_embeddings = [embed_query(t) for t in chunk_texts]
    similarities = [
        float(np.dot(answer_embedding, ce) /
              (np.linalg.norm(answer_embedding) * np.linalg.norm(ce) + 1e-9))
        for ce in chunk_embeddings
    ]
    max_similarity = max(similarities)
    print(f"[Grounding] Max answer-chunk similarity: {max_similarity:.3f}")
    return max_similarity >= threshold


def run_query(
    repo_id: str,
    query: str,
    clone_result: dict,
    conversation_history: list[dict] = None,
) -> dict:
    if conversation_history is None:
        conversation_history = []

    print(f"[Chain] Running retrieval with expansion...")
    # retrieval_result = retrieve_with_expansion(repo_id, query)
    print(f"[Chain] Generating hypothetical answer for retrieval (HyDE)...")
    hypothetical = generate_hypothetical_answer(query)
    retrieval_query = f"{query}\n\n{hypothetical}"
    retrieval_result = retrieve_with_expansion(repo_id, retrieval_query)
    chunks = retrieval_result["chunks"]

    if not chunks:
        return {
            "answer": "I could not find relevant code in this repository to answer your question. Try rephrasing or asking about a specific function or file.",
            "sources": [],
            "retrieved_count": 0,
            "expanded_count": 0,
        }

    # retrieved = [c for c in chunks if not c.get("is_expanded")]
    # expanded = [c for c in chunks if c.get("is_expanded")]
    # retrieved = retrieved[:4]
    # expanded = expanded[:2]
    # chunks_for_llm = retrieved + expanded

    chunks_for_llm = chunks

    for chunk in chunks_for_llm:
        chunk["document"] = truncate_chunk_text(chunk["document"], MAX_CHUNK_CHARS)

    print(f"[Chain] Sending {len(chunks_for_llm)} chunks to LLM (4 retrieved + up to 2 expanded)")

    context = format_context(chunks_for_llm)
    history_text = format_conversation_history(conversation_history[-2:])

    print(f"[Chain] Calling LLM...")
    chain = build_chain()
    answer = chain.invoke({
        "context": context,
        "question": query,
        "conversation_history": history_text,
    })

    sources = format_sources(chunks, clone_result)

    # grounded = is_answer_grounded(answer, chunks_for_llm)
    # if not grounded:
    #     answer = (
    #         "⚠ Low confidence: The retrieved code chunks may not fully support this answer. "
    #         "Try rephrasing with more specific function or file names.\n\n" + answer
    #     )

    print(f"[Chain] Done. Answer length: {len(answer)} chars")
    return {
        "answer": answer,
        "sources": sources,
        "retrieved_count": retrieval_result["retrieved_count"],
        "expanded_count": retrieval_result["expanded_count"],
    }