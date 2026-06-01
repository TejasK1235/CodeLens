import os
import hashlib
import time
from app.config import MAX_CHUNK_TOKENS, MIN_CHUNK_WORDS

def generate_file_description(file_path: str, function_names: list[str]) -> str:
    from langchain_groq import ChatGroq
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from app.config import GROQ_API_KEY, GROQ_MODEL_QUERY

    llm = ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL_QUERY,
        temperature=0.1,
        max_tokens=80,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a code documentation assistant. Given a file path and its "
         "function/class names, write exactly one sentence describing what this "
         "file does in the overall system. Be specific and technical. "
         "Do not start with 'This file'. Start with the module's purpose directly."
        ),
        ("human",
         "File: {file_path}\n"
         "Functions and classes: {functions}\n\n"
         "One sentence description:"
        ),
    ])
    chain = prompt | llm | StrOutputParser()
    try:
        time.sleep(0.5)
        description = chain.invoke({
            "file_path": file_path,
            "functions": ", ".join(function_names[:10]),
        })
        return description.strip()
    except Exception as e:
        print(f"[Chunker] LLM description failed for {file_path}: {e}")
        return f"Module containing: {', '.join(function_names[:5])}"

def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


def split_large_chunk(chunk: dict, max_tokens: int) -> list[dict]:
    lines = chunk["text"].split("\n")
    sub_chunks = []
    current_lines = []
    current_tokens = 0
    part = 0

    for line in lines:
        line_tokens = estimate_tokens(line)
        if current_tokens + line_tokens > max_tokens and current_lines:
            text = "\n".join(current_lines)
            sub_chunk = chunk.copy()
            sub_chunk["text"] = text
            sub_chunk["name"] = f"{chunk['name']}_part{part}"
            sub_chunk["type"] = chunk["type"] + "_split"
            sub_chunks.append(sub_chunk)
            current_lines = [line]
            current_tokens = line_tokens
            part += 1
        else:
            current_lines.append(line)
            current_tokens += line_tokens

    if current_lines:
        text = "\n".join(current_lines)
        sub_chunk = chunk.copy()
        sub_chunk["text"] = text
        sub_chunk["name"] = f"{chunk['name']}_part{part}"
        sub_chunk["type"] = chunk["type"] + "_split"
        sub_chunks.append(sub_chunk)

    return sub_chunks


def make_chunk_id(repo_id: str, file_path: str, name: str, start_line: int) -> str:
    raw = f"{repo_id}:{file_path}:{name}:{start_line}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def process_chunks(raw_chunks: list[dict], repo_id: str) -> list[dict]:
    final_chunks = []
    oversized = 0
    undersized = 0

    for chunk in raw_chunks:
        word_count = len(chunk["text"].split())
        if word_count < MIN_CHUNK_WORDS:
            undersized += 1
            continue

        token_estimate = estimate_tokens(chunk["text"])
        if token_estimate > MAX_CHUNK_TOKENS:
            oversized += 1
            sub_chunks = split_large_chunk(chunk, MAX_CHUNK_TOKENS)
            for sc in sub_chunks:
                if len(sc["text"].split()) >= MIN_CHUNK_WORDS:
                    sc["chunk_id"] = make_chunk_id(
                        repo_id,
                        sc["file_path"],
                        sc["name"],
                        sc["start_line"],
                    )
                    sc["repo_id"] = repo_id
                    final_chunks.append(sc)
        else:
            chunk["chunk_id"] = make_chunk_id(
                repo_id,
                chunk["file_path"],
                chunk["name"],
                chunk["start_line"],
            )
            chunk["repo_id"] = repo_id
            final_chunks.append(chunk)

    from collections import defaultdict

    file_groups = defaultdict(list)
    for chunk in final_chunks:
        file_groups[chunk["file_path"]].append(chunk)

    for file_path, file_chunks in file_groups.items():
        summary = build_file_summary_chunk(file_path, file_chunks, repo_id)
        if summary:
            final_chunks.append(summary)

    print(f"[Chunker] Added {len(file_groups)} file summary chunks")

    print(f"[Chunker] Input: {len(raw_chunks)} raw chunks")
    print(f"[Chunker] Dropped {undersized} undersized chunks")
    print(f"[Chunker] Split {oversized} oversized chunks")
    print(f"[Chunker] Output: {len(final_chunks)} final chunks")
    return final_chunks


def build_file_summary_chunk(file_path: str, chunks: list[dict], repo_id: str) -> dict | None:
    if not chunks:
        return None
    function_names = [c["name"] for c in chunks if c["type"] not in ("module", "file_summary", "markdown_section")]
    if len(function_names) < 2:
        return None

    file_name = os.path.basename(file_path)
    parent_dir = os.path.basename(os.path.dirname(file_path))

    print(f"[Chunker] Generating description for {file_path}...")
    description = generate_file_description(file_path, function_names)

    summary_text = (
        f"# Module: {file_path}\n\n"
        f"{description}\n\n"
        f"Contains {len(function_names)} functions and classes: "
        f"{', '.join(function_names[:20])}{'...' if len(function_names) > 20 else ''}.\n"
        f"Part of the {parent_dir} layer of the system."
    )
    return {
        "name": f"__file__{parent_dir}__{file_name}",
        "type": "file_summary",
        "text": summary_text,
        "file_path": file_path,
        "start_line": 1,
        "end_line": chunks[-1].get("end_line", 1),
        "language": chunks[0].get("language", "unknown"),
        "imports": [],
        "calls": function_names,
        "chunk_id": make_chunk_id(repo_id, file_path, "__file_summary__", 0),
        "repo_id": repo_id,
    }


def build_chunk_document(chunk: dict) -> str:
    header = f"# {chunk['name']} ({chunk['type']}) in {chunk['file_path']}"
    return f"{header}\n\n{chunk['text']}"