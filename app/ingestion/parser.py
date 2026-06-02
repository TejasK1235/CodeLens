import os
import re
import json
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from app.config import SUPPORTED_EXTENSIONS

PY_LANGUAGE = Language(tspython.language(), "python")
JS_LANGUAGE = Language(tsjavascript.language(), "javascript")

TS_LANGUAGE = None
try:
    import tree_sitter_typescript as tsts
    TS_LANGUAGE = Language(tsts.language_typescript(), "typescript")
except Exception:
    pass

LANGUAGE_MAP = {".py": PY_LANGUAGE, ".js": JS_LANGUAGE}
if TS_LANGUAGE:
    LANGUAGE_MAP[".ts"] = TS_LANGUAGE

PY_CHUNK_TYPES = {"function_definition", "class_definition"}
JS_CHUNK_TYPES = {
    "function_declaration", "function_expression", "arrow_function",
    "class_declaration", "method_definition",
}
TS_CHUNK_TYPES = JS_CHUNK_TYPES

CHUNK_TYPES_MAP = {".py": PY_CHUNK_TYPES, ".js": JS_CHUNK_TYPES}
if TS_LANGUAGE:
    CHUNK_TYPES_MAP[".ts"] = TS_CHUNK_TYPES

PLAIN_TEXT_EXTENSIONS = {".java", ".cpp", ".cs"}


# ── Comment stripping ─────────────────────────────────────────────────────────

def strip_comments(text: str, ext: str) -> str:
    if ext == ".py":
        lines = text.split("\n")
        return "\n".join(
            line for line in lines
            if not re.match(r'^\s*#', line.rstrip())
        )
    elif ext in (".js", ".ts", ".java", ".cpp", ".cs"):
        text = re.sub(r'//[^\n]*', '', text)
        text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
        return text
    return text


# ── Context extraction for contextual chunking ────────────────────────────────

def extract_class_context(node, source_bytes: bytes, ext: str) -> dict | None:
    """
    Walk up the AST from a method/function node to find if it lives inside
    a class. If so, return the class name and the attributes defined in __init__
    (Python) or the constructor (JS/TS).
    """
    # tree-sitter nodes have a parent attribute in newer versions,
    # but we do it by re-walking from root to find the enclosing class.
    # We store context during the visit() traversal instead — see parse_file().
    return None


def extract_init_attributes(class_node, source_bytes: bytes, ext: str) -> list[str]:
    """
    Extract self.x assignments from __init__ (Python) or this.x from
    constructor (JS/TS) so we can add them to the context prefix.
    """
    attrs = []

    def find_init(node):
        if ext == ".py":
            if node.type == "function_definition":
                name_node = next(
                    (c for c in node.children if c.type == "identifier"), None
                )
                if name_node:
                    name = source_bytes[
                        name_node.start_byte:name_node.end_byte
                    ].decode("utf-8", errors="replace")
                    if name == "__init__":
                        collect_self_attrs(node)
                        return
        elif ext in (".js", ".ts"):
            if node.type == "method_definition":
                name_node = next(
                    (c for c in node.children if c.type == "property_identifier"), None
                )
                if name_node:
                    name = source_bytes[
                        name_node.start_byte:name_node.end_byte
                    ].decode("utf-8", errors="replace")
                    if name == "constructor":
                        collect_this_attrs(node)
                        return
        for child in node.children:
            find_init(child)

    def collect_self_attrs(init_node):
        # Find all `self.x = ...` assignments
        def scan(n):
            if n.type == "assignment":
                left = n.children[0] if n.children else None
                if left and left.type == "attribute":
                    obj = left.children[0] if left.children else None
                    attr = left.children[-1] if left.children else None
                    if obj and attr:
                        obj_text = source_bytes[
                            obj.start_byte:obj.end_byte
                        ].decode("utf-8", errors="replace")
                        if obj_text == "self":
                            attr_text = source_bytes[
                                attr.start_byte:attr.end_byte
                            ].decode("utf-8", errors="replace")
                            attrs.append(attr_text)
            for child in n.children:
                scan(child)
        scan(init_node)

    def collect_this_attrs(ctor_node):
        def scan(n):
            if n.type == "assignment_expression":
                left = n.children[0] if n.children else None
                if left and left.type == "member_expression":
                    obj_text = source_bytes[
                        left.children[0].start_byte:left.children[0].end_byte
                    ].decode("utf-8", errors="replace") if left.children else ""
                    if obj_text == "this" and len(left.children) > 2:
                        attr_text = source_bytes[
                            left.children[-1].start_byte:left.children[-1].end_byte
                        ].decode("utf-8", errors="replace")
                        attrs.append(attr_text)
            for child in n.children:
                scan(child)
        scan(ctor_node)

    find_init(class_node)
    # deduplicate while preserving order
    seen = set()
    result = []
    for a in attrs:
        if a not in seen:
            seen.add(a)
            result.append(a)
    return result[:12]  # cap at 12 to avoid bloating context


def build_context_prefix(
    chunk_name: str,
    class_name: str | None,
    class_attrs: list[str],
    file_path: str,
    ext: str,
) -> str:
    """
    Build the context prefix that gets prepended to a method/function chunk.
    Only adds real information — skips lines that would be empty.
    """
    lines = []
    if class_name:
        lines.append(f"[Class: {class_name} | File: {file_path}]")
        if class_attrs:
            lines.append(f"[Instance attributes: {', '.join(class_attrs)}]")
        lines.append(f"[Method: {chunk_name}]")
    else:
        lines.append(f"[Function: {chunk_name} | File: {file_path}]")
    return "\n".join(lines)


# ── Markdown, ipynb, plain-text parsers (unchanged) ──────────────────────────

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
            "context_prefix": "",
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
                "context_prefix": "",
            })
        elif cell_type == "code":
            cleaned = strip_comments(source, ".py")
            code_cells.append((i, cleaned))

    if code_cells:
        combined = "\n\n".join(text for _, text in code_cells)
        if len(combined.split()) >= 5:
            chunks.append({
                "name": f"{os.path.basename(file_path)}_code",
                "type": "notebook_code",
                "text": combined,
                "file_path": relative_path,
                "start_line": code_cells[0][0],
                "end_line": code_cells[-1][0],
                "language": "py",
                "imports": [],
                "calls": [],
                "context_prefix": "",
            })
    return chunks


def parse_plain_text_file(
    file_path: str, source_bytes: bytes, repo_root: str, ext: str
) -> list[dict]:
    relative_path = os.path.relpath(file_path, repo_root)
    text = source_bytes.decode("utf-8", errors="replace")
    cleaned = strip_comments(text, ext)
    lines = cleaned.split("\n")
    chunks = []
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
                    "context_prefix": "",
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
                "context_prefix": "",
            })
    return chunks


# ── Helpers ───────────────────────────────────────────────────────────────────

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
    parser = Parser()
    parser.set_language(language)  
    tree = parser.parse(source_bytes)
    imports = []

    def visit(node):
        if ext == ".py" and node.type in ("import_statement", "import_from_statement"):
            imports.append(
                source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
            )
        if ext in (".js", ".ts") and node.type == "import_statement":
            imports.append(
                source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
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


# ── Main file parser — contextual chunking lives here ────────────────────────

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
    parser = Parser()
    parser.set_language(language)

    try:
        tree = parser.parse(source_bytes)
    except Exception as e:
        print(f"[Parser] tree-sitter failed on {file_path}: {e}")
        return []

    relative_path = os.path.relpath(file_path, repo_root)
    imports = extract_imports(source_bytes, ext)
    chunks = []

    # ── Contextual chunking: track enclosing class during traversal ──────────
    # We pass class_context down through the visit() recursion so that when we
    # hit a method inside a class, we already have the class name and its
    # __init__ attributes available to build a context prefix.

    def visit(node, class_context: dict | None = None):
        """
        class_context = {
            "name": str,          # class name
            "attrs": list[str],   # instance attributes from __init__/constructor
        } | None
        """
        is_class = (
            (ext == ".py" and node.type == "class_definition") or
            (ext in (".js", ".ts") and node.type == "class_declaration")
        )

        if is_class:
            class_name = get_node_name(node, source_bytes)
            attrs = extract_init_attributes(node, source_bytes, ext)
            new_context = {"name": class_name, "attrs": attrs}

            # Emit the class definition itself as a chunk (the header + body)
            raw_text = source_bytes[node.start_byte:node.end_byte].decode(
                "utf-8", errors="replace"
            )
            cleaned_text = strip_comments(raw_text, ext)
            calls = extract_calls(node, source_bytes)
            prefix = build_context_prefix(class_name, None, [], relative_path, ext)
            # For class-level chunks we don't prepend a method prefix,
            # just label it as the class itself
            prefix = f"[Class definition: {class_name} | File: {relative_path}]"
            chunks.append({
                "name": class_name,
                "type": node.type,
                "text": cleaned_text,
                "file_path": relative_path,
                "start_line": node.start_point[0] + 1,
                "end_line": node.end_point[0] + 1,
                "language": ext.lstrip("."),
                "imports": imports,
                "calls": calls,
                "context_prefix": prefix,
            })

            # Recurse into class body with class context — methods will pick it up
            for child in node.children:
                visit(child, new_context)
            return

        is_function = node.type in chunk_types and not is_class
        if is_function:
            name = get_node_name(node, source_bytes)
            raw_text = source_bytes[node.start_byte:node.end_byte].decode(
                "utf-8", errors="replace"
            )
            cleaned_text = strip_comments(raw_text, ext)
            calls = extract_calls(node, source_bytes)

            # Build contextual prefix — the key addition
            if class_context:
                prefix = build_context_prefix(
                    name,
                    class_context["name"],
                    class_context["attrs"],
                    relative_path,
                    ext,
                )
            else:
                prefix = build_context_prefix(name, None, [], relative_path, ext)

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
                "context_prefix": prefix,
            })
            # Do not recurse further — nested functions become their own chunks
            return

        # Not a class or function node — recurse with same context
        for child in node.children:
            visit(child, class_context)

    visit(tree.root_node)

    # Fallback: if no chunks were extracted, store the whole file as one chunk
    if not chunks:
        text = source_bytes.decode("utf-8", errors="replace")
        cleaned = strip_comments(text, ext)
        if len(cleaned.split()) >= 5:
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
                "context_prefix": f"[Module: {os.path.basename(file_path)} | File: {relative_path}]",
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
            file_chunks = parse_file(file_path, clone_path)
            if file_chunks:
                all_chunks.extend(file_chunks)
                parsed_files += 1
            else:
                skipped += 1

    print(f"[Parser] Parsed {parsed_files} files → {len(all_chunks)} raw chunks")
    print(f"[Parser] Skipped {skipped} files (unsupported or empty)")
    return all_chunks