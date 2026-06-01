import os
import re
import json
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from app.config import SUPPORTED_EXTENSIONS

PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())

TS_LANGUAGE = None
try:
    import tree_sitter_typescript as tsts
    TS_LANGUAGE = Language(tsts.language_typescript())
except Exception:
    pass

LANGUAGE_MAP = {
    ".py": PY_LANGUAGE,
    ".js": JS_LANGUAGE,
}
if TS_LANGUAGE:
    LANGUAGE_MAP[".ts"] = TS_LANGUAGE

PY_CHUNK_TYPES = {"function_definition", "class_definition"}
JS_CHUNK_TYPES = {
    "function_declaration",
    "function_expression",
    "arrow_function",
    "class_declaration",
    "method_definition",
}
TS_CHUNK_TYPES = JS_CHUNK_TYPES

CHUNK_TYPES_MAP = {
    ".py": PY_CHUNK_TYPES,
    ".js": JS_CHUNK_TYPES,
}
if TS_LANGUAGE:
    CHUNK_TYPES_MAP[".ts"] = TS_CHUNK_TYPES

PLAIN_TEXT_EXTENSIONS = {".java", ".cpp", ".cs"}


def strip_comments(text: str, ext: str) -> str:
    if ext == ".py":
        lines = text.split("\n")
        stripped = []
        for line in lines:
            if re.match(r'^\s*#', line.rstrip()):
                continue
            stripped.append(line)
        return "\n".join(stripped)
    elif ext in (".js", ".ts", ".java", ".cpp", ".cs"):
        text = re.sub(r'//[^\n]*', '', text)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        return text
    return text


def parse_markdown_file(file_path: str, source_bytes: bytes, repo_root: str) -> list[dict]:
    relative_path = os.path.relpath(file_path, repo_root)
    text = source_bytes.decode("utf-8", errors="replace")
    sections = re.split(r'\n(?=#{1,3} )', text)
    chunks = []
    for i, section in enumerate(sections):
        section = section.strip()
        if len(section.split()) < 5:
            continue
        lines = section.split("\n")
        heading = lines[0].lstrip("#").strip()
        name = heading[:60] if heading else f"section_{i}"
        chunks.append({
            "name": name,
            "type": "markdown_section",
            "text": section,
            "file_path": relative_path,
            "start_line": 1,
            "end_line": len(lines),
            "language": "md",
            "imports": [],
            "calls": [],
        })
    return chunks


def parse_ipynb_file(file_path: str, source_bytes: bytes, repo_root: str) -> list[dict]:
    relative_path = os.path.relpath(file_path, repo_root)
    try:
        nb = json.loads(source_bytes.decode("utf-8", errors="replace"))
    except Exception:
        return []

    chunks = []
    cells = nb.get("cells", [])
    code_cells = []

    for i, cell in enumerate(cells):
        cell_type = cell.get("cell_type", "")
        source = "".join(cell.get("source", []))
        if not source.strip() or len(source.split()) < 5:
            continue
        if cell_type == "markdown":
            chunks.append({
                "name": f"markdown_cell_{i}",
                "type": "markdown_section",
                "text": source,
                "file_path": relative_path,
                "start_line": i,
                "end_line": i,
                "language": "md",
                "imports": [],
                "calls": [],
            })
        elif cell_type == "code":
            cleaned = strip_comments(source, ".py")
            code_cells.append((i, cleaned))

    if code_cells:
        combined = "\n\n".join(f"# Cell {idx}\n{code}" for idx, code in code_cells)
        chunks.append({
            "name": f"notebook_code_{os.path.basename(file_path)}",
            "type": "notebook_code",
            "text": combined,
            "file_path": relative_path,
            "start_line": 1,
            "end_line": len(cells),
            "language": "py",
            "imports": [],
            "calls": [],
        })

    return chunks


def parse_plain_text_file(file_path: str, source_bytes: bytes, repo_root: str, ext: str) -> list[dict]:
    relative_path = os.path.relpath(file_path, repo_root)
    text = source_bytes.decode("utf-8", errors="replace")
    text = strip_comments(text, ext)
    chunks = []
    lines = text.split("\n")
    current_block = []
    current_start = 1

    for i, line in enumerate(lines, 1):
        current_block.append(line)
        if len(current_block) >= 40:
            block_text = "\n".join(current_block).strip()
            if len(block_text.split()) >= 5:
                chunks.append({
                    "name": f"{os.path.basename(file_path)}_block_{len(chunks)}",
                    "type": "code_block",
                    "text": block_text,
                    "file_path": relative_path,
                    "start_line": current_start,
                    "end_line": i,
                    "language": ext.lstrip("."),
                    "imports": [],
                    "calls": [],
                })
            current_block = []
            current_start = i + 1

    if current_block:
        block_text = "\n".join(current_block).strip()
        if len(block_text.split()) >= 5:
            chunks.append({
                "name": f"{os.path.basename(file_path)}_block_{len(chunks)}",
                "type": "code_block",
                "text": block_text,
                "file_path": relative_path,
                "start_line": current_start,
                "end_line": len(lines),
                "language": ext.lstrip("."),
                "imports": [],
                "calls": [],
            })

    return chunks


def get_node_name(node, source_bytes: bytes) -> str:
    for child in node.children:
        if child.type == "identifier":
            return source_bytes[child.start_byte:child.end_byte].decode(
                "utf-8", errors="replace"
            )
    return "anonymous"


def extract_imports(source_bytes: bytes, ext: str) -> list[str]:
    language = LANGUAGE_MAP.get(ext)
    if not language:
        return []
    parser = Parser(language)
    tree = parser.parse(source_bytes)
    imports = []

    def visit(node):
        if ext == ".py" and node.type in ("import_statement", "import_from_statement"):
            imports.append(
                source_bytes[node.start_byte:node.end_byte].decode(
                    "utf-8", errors="replace"
                )
            )
        if ext in (".js", ".ts") and node.type == "import_statement":
            imports.append(
                source_bytes[node.start_byte:node.end_byte].decode(
                    "utf-8", errors="replace"
                )
            )
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return imports


def extract_calls(node, source_bytes: bytes) -> list[str]:
    calls = []

    def visit(n):
        if n.type == "call":
            for child in n.children:
                if child.type in ("identifier", "attribute"):
                    call_text = source_bytes[
                        child.start_byte:child.end_byte
                    ].decode("utf-8", errors="replace")
                    calls.append(call_text)
                    break
        for child in n.children:
            visit(child)

    visit(node)
    return list(set(calls))


def parse_file(file_path: str, repo_root: str) -> list[dict]:
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return []

    try:
        with open(file_path, "rb") as f:
            source_bytes = f.read()
    except Exception as e:
        print(f"[Parser] Could not read {file_path}: {e}")
        return []

    if len(source_bytes) == 0:
        return []

    if ext == ".md":
        return parse_markdown_file(file_path, source_bytes, repo_root)

    if ext == ".ipynb":
        return parse_ipynb_file(file_path, source_bytes, repo_root)

    if ext in PLAIN_TEXT_EXTENSIONS:
        return parse_plain_text_file(file_path, source_bytes, repo_root, ext)

    language = LANGUAGE_MAP.get(ext)
    if not language:
        return []

    chunk_types = CHUNK_TYPES_MAP.get(ext, set())
    parser = Parser(language)

    try:
        tree = parser.parse(source_bytes)
    except Exception as e:
        print(f"[Parser] tree-sitter failed on {file_path}: {e}")
        return []

    relative_path = os.path.relpath(file_path, repo_root)
    imports = extract_imports(source_bytes, ext)
    chunks = []

    def visit(node):
        if node.type in chunk_types:
            name = get_node_name(node, source_bytes)
            raw_text = source_bytes[node.start_byte:node.end_byte].decode(
                "utf-8", errors="replace"
            )
            cleaned_text = strip_comments(raw_text, ext)
            calls = extract_calls(node, source_bytes)
            chunks.append({
                "name": name,
                "type": node.type,
                "text": cleaned_text,
                "file_path": relative_path,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "language": ext.lstrip("."),
                "imports": imports,
                "calls": calls,
            })
        else:
            for child in node.children:
                visit(child)

    visit(tree.root_node)

    if not chunks:
        text = source_bytes.decode("utf-8", errors="replace")
        cleaned = strip_comments(text, ext)
        word_count = len(cleaned.split())
        if word_count >= 5:
            chunks.append({
                "name": os.path.basename(file_path),
                "type": "module",
                "text": cleaned,
                "file_path": relative_path,
                "start_line": 1,
                "end_line": source_bytes.count(b"\n") + 1,
                "language": ext.lstrip("."),
                "imports": imports,
                "calls": [],
            })

    return chunks


def parse_repo(clone_path: str) -> list[dict]:
    all_chunks = []
    skipped = 0
    parsed_files = 0

    for root, dirs, files in os.walk(clone_path):
        dirs[:] = [
            d for d in dirs
            if d not in {
                ".git", "node_modules", "__pycache__",
                ".venv", "venv", "dist", "build", ".next",
                ".ipynb_checkpoints",
            }
        ]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                skipped += 1
                continue
            file_path = os.path.join(root, filename)
            chunks = parse_file(file_path, clone_path)
            if chunks:
                all_chunks.extend(chunks)
                parsed_files += 1
            else:
                skipped += 1

    print(f"[Parser] Parsed {parsed_files} files → {len(all_chunks)} raw chunks")
    print(f"[Parser] Skipped {skipped} files (unsupported or empty)")
    return all_chunks