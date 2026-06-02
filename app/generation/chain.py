from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from app.config import GROQ_API_KEY, GROQ_MODEL_QUERY
from app.generation.prompts import (
    build_qa_prompt,
    format_context,
    format_conversation_history,
    SYSTEM_PROMPT,
    GRIEVOUS_SYSTEM_PROMPT,
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


def build_chain(grievous_mode: bool = False):
    from langchain_groq import ChatGroq
    from langchain_core.output_parsers import StrOutputParser
     
    system = GRIEVOUS_SYSTEM_PROMPT if grievous_mode else SYSTEM_PROMPT
    prompt = build_qa_prompt(system_prompt=system)
 
    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL_QUERY,
        temperature=0.7 if grievous_mode else 0.1,  # more creative in Grievous mode
        max_tokens=1024,
        stop_sequences=["Note that"],
    )
 
    return prompt | llm | StrOutputParser()


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
        if chunk.get("type") == "file_summary":
            continue
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
    conversation_history: list = None,
    grievous_mode: bool = False,
) -> dict:
    conversation_history = conversation_history or []
 
    # HyDE — generate hypothetical answer to enrich retrieval
    hypothetical = generate_hypothetical_answer(query)
    enriched_query = f"{query}\n\n{hypothetical}" if hypothetical else query
 
    # Retrieve with expansion
    retrieval_result = retrieve_with_expansion(repo_id, enriched_query)
    chunks = retrieval_result["chunks"]
 
    if not chunks:
        return {
            "answer": "I could not find relevant code chunks for your query. "
                      "The repository may not be fully indexed yet.",
            "sources": [],
            "retrieved_count": 0,
            "expanded_count": 0,
        }
 
    context = format_context(chunks)
    history_text = format_conversation_history(conversation_history)
 
    # Build chain — use Grievous system prompt if in easter egg mode
    chain = build_chain(grievous_mode=grievous_mode)
 
    try:
        answer = chain.invoke({
            "context": context,
            "conversation_history": history_text,
            "question": query,
        })
    except Exception as e:
        print(f"[Chain] LLM error: {e}")
        answer = f"LLM error: {str(e)}"
 
    sources = format_sources(chunks, clone_result)
 
    return {
        "answer": answer,
        "sources": sources,
        "retrieved_count": retrieval_result["retrieved_count"],
        "expanded_count": retrieval_result["expanded_count"],
    }
