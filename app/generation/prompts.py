from langchain_core.prompts import ChatPromptTemplate

SYSTEM_PROMPT = """You are CodeLens, an expert code assistant that answers questions about a specific software repository.

You will be given:
1. A question about the codebase
2. Relevant code chunks retrieved from the repository (with file paths and function names)
3. Optionally, conversation history for follow-up questions

Your job is to answer the question accurately using ONLY the provided code chunks as your source of truth.

Rules:
- Base your answer strictly on the provided code chunks. Do not invent code or behaviour that is not shown.
- Always reference specific function names and file paths in your answer.
- If the code chunks do not contain enough information to answer fully, say so clearly.
- When explaining how something works, walk through the actual code logic, not a generic description.
- Keep answers concise but complete. Use bullet points for multi-step explanations.
- Do not repeat the question back to the user.
- If a follow-up question refers to something from the conversation history, use that context.
"""

HUMAN_PROMPT = """CONVERSATION HISTORY:
{conversation_history}

RETRIEVED CODE CHUNKS:
{context}

QUESTION:
{question}

Answer based on the code chunks above:"""


def build_qa_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", HUMAN_PROMPT),
    ])


def format_context(chunks: list[dict]) -> str:
    sections = []
    for i, chunk in enumerate(chunks):
        tag = "[EXPANDED]" if chunk.get("is_expanded") else "[RETRIEVED]"
        similarity = chunk.get("similarity")
        sim_str = f"similarity: {similarity}" if similarity is not None else "via dependency expansion"

        header = (
            f"--- Chunk {i+1} {tag} ---\n"
            f"Function: {chunk['name']}\n"
            f"File: {chunk['file_path']} (lines {chunk['start_line']}–{chunk['end_line']})\n"
            f"Match: {sim_str}\n"
        )
        sections.append(header + "\n" + chunk["document"])

    return "\n\n".join(sections)


def format_conversation_history(history: list[dict]) -> str:
    if not history:
        return "No previous conversation."
    lines = []
    for turn in history:
        lines.append(f"User: {turn['query']}")
        lines.append(f"Assistant: {turn['answer']}")
    return "\n".join(lines)