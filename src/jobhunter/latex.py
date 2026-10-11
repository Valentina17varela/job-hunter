"""Master CV parser and assembler (see specs/06-tailoring.md §2).

``master.tex`` is the person's own LaTeX CV plus ``% jh:`` marker comments:

    % jh:section experience
    \\section{Experience}
    % jh:entry exp-acme required
    \\cventry{2022--Present}{Engineer}{Acme}{}{}{
    \\begin{itemize}
    % jh:item exp-acme-1 tags=python,aws
    \\item Cut latency by 40\\%.
    % jh:item exp-acme-2
    \\item Built X.
    \\end{itemize}}
    % jh:endentry
    % jh:endsection

Everything outside markers is copied verbatim and is never sent to an LLM.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

MARKER_RE = re.compile(r"^\s*%\s*jh:(\w+)\s*(.*?)\s*$")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class CvError(Exception):
    """The master CV markers are malformed."""


@dataclass
class Item:
    id: str
    tags: list[str]
    lines: list[str]  # the item's own LaTeX
    tail: list[str] = field(default_factory=list)  # text after it, up to the next sibling


@dataclass
class Entry:
    id: str
    required: bool
    head: list[str] = field(default_factory=list)
    items: list[Item] = field(default_factory=list)
    suffix: list[str] = field(default_factory=list)
    tail: list[str] = field(default_factory=list)


@dataclass
class Section:
    name: str
    head: list[str] = field(default_factory=list)
    children: list[Entry | Item] = field(default_factory=list)
    suffix: list[str] = field(default_factory=list)


@dataclass
class Document:
    nodes: list[list[str] | Section]  # raw text blocks and sections, in file order
    source_hash: str

    @property
    def sections(self) -> list[Section]:
        return [n for n in self.nodes if isinstance(n, Section)]

    def ids(self) -> list[str]:
        out: list[str] = []
        for section in self.sections:
            for child in section.children:
                out.append(child.id)
                if isinstance(child, Entry):
                    out.extend(i.id for i in child.items)
        return out


def _is_marker(line: str) -> tuple[str, str] | None:
    m = MARKER_RE.match(line)
    return (m.group(1), m.group(2)) if m else None


def _parse_args(rest: str) -> tuple[list[str], dict[str, str]]:
    words, opts = [], {}
    for token in rest.split():
        if "=" in token:
            key, _, value = token.partition("=")
            opts[key] = value
        else:
            words.append(token)
    return words, opts


def parse(text: str) -> Document:
    """Parse marked LaTeX into a Document. Raises CvError on malformed markers."""
    lines = text.splitlines()
    nodes: list[list[str] | Section] = []
    raw: list[str] = []
    i = 0
    n = len(lines)

    def read_item(start: int, name: str, tags: list[str]) -> tuple[Item, int]:
        j = start
        block: list[str] = []
        while j < n:
            line = lines[j]
            stripped = line.strip()
            if _is_marker(line) or stripped.startswith("\\end{"):
                break
            if block and (stripped.startswith("\\item") or not stripped):
                break  # next bullet, or a blank line ends the item
            block.append(line)
            j += 1
        if not block:
            raise CvError(f"item '{name}' has no content")
        return Item(name, tags, block), j

    def collect_text(start: int) -> tuple[list[str], int]:
        j, text_lines = start, []
        while j < n and not _is_marker(lines[j]):
            text_lines.append(lines[j])
            j += 1
        return text_lines, j

    while i < n:
        marker = _is_marker(lines[i])
        if marker is None:
            raw.append(lines[i])
            i += 1
            continue
        kind, rest = marker
        if kind != "section":
            raise CvError(f"line {i + 1}: '% jh:{kind}' outside a section")
        words, _ = _parse_args(rest)
        if not words:
            raise CvError(f"line {i + 1}: section needs a name")
        if raw:
            nodes.append(raw)
            raw = []
        section = Section(words[0])
        head, i = collect_text(i + 1)
        section.head = head
        while True:
            if i >= n:
                raise CvError(f"section '{section.name}' is missing '% jh:endsection'")
            kind2, rest2 = _is_marker(lines[i]) or ("", "")
            if kind2 == "endsection":
                i += 1
                break
            if kind2 == "item":
                words2, opts = _parse_args(rest2)
                if not words2:
                    raise CvError(f"line {i + 1}: item needs an id")
                tags = [t for t in opts.get("tags", "").split(",") if t]
                item, i = read_item(i + 1, words2[0], tags)
                section.children.append(item)
                tail, i = collect_text(i)
                item.tail = tail
                continue
            if kind2 == "entry":
                words2, _ = _parse_args(rest2)
                if not words2:
                    raise CvError(f"line {i + 1}: entry needs an id")
                entry = Entry(words2[0], "required" in words2[1:])
                entry.head, i = collect_text(i + 1)
                while True:
                    if i >= n:
                        raise CvError(f"entry '{entry.id}' is missing '% jh:endentry'")
                    kind3, rest3 = _is_marker(lines[i]) or ("", "")
                    if kind3 == "endentry":
                        i += 1
                        break
                    if kind3 != "item":
                        raise CvError(
                            f"line {i + 1}: unexpected '% jh:{kind3}' in entry '{entry.id}'"
                        )
                    words3, opts3 = _parse_args(rest3)
                    if not words3:
                        raise CvError(f"line {i + 1}: item needs an id")
                    tags3 = [t for t in opts3.get("tags", "").split(",") if t]
                    item, i = read_item(i + 1, words3[0], tags3)
                    entry.items.append(item)
                    tail, i = collect_text(i)
                    item.tail = tail
                if entry.items:  # text after the last item belongs to the entry, not the item
                    entry.suffix = entry.items[-1].tail
                    entry.items[-1].tail = []
                section.children.append(entry)
                entry.tail, i = collect_text(i)
                continue
            raise CvError(f"line {i + 1}: unexpected '% jh:{kind2}' in section '{section.name}'")
        if section.children:
            last = section.children[-1]
            section.suffix = last.tail
            last.tail = []
        else:
            section.suffix = []
        nodes.append(section)
    if raw:
        nodes.append(raw)
    doc = Document(nodes, hashlib.sha256(text.encode()).hexdigest())
    names = [s.name for s in doc.sections]
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise CvError(f"duplicate section names: {', '.join(repeated)}")
    ids = doc.ids()
    dupes = sorted({x for x in ids if ids.count(x) > 1})
    if dupes:
        raise CvError(f"duplicate ids: {', '.join(dupes)}")
    return doc


# --- plain text for the LLM ------------------------------------------------------------------

_CMD_WITH_TEXT = re.compile(
    r"\\(?:textbf|textit|emph|underline|textsc|texttt|small|large)\s*\{([^{}]*)\}"
)
_HREF = re.compile(r"\\href\{[^{}]*\}\{([^{}]*)\}")
_ENV = re.compile(r"\\(?:begin|end)\{[^{}]*\}(?:\[[^\]]*\])?")
_ANY_CMD = re.compile(r"\\[a-zA-Z]+\*?")


def to_plain(latex: str) -> str:
    """Readable text from a LaTeX fragment (comments, commands and braces removed)."""
    text = "\n".join(re.sub(r"(?<!\\)%.*$", "", ln) for ln in latex.splitlines())
    for _ in range(3):
        text = _HREF.sub(r"\1", text)
        text = _CMD_WITH_TEXT.sub(r"\1", text)
    text = re.sub(r"^\s*[•·▪‣-]\s+", "", text, flags=re.M)  # plain-text bullets
    text = _ENV.sub(" ", text)
    text = re.sub(r"\\\\\s*\[[^\]]*\]", " ", text)  # line breaks with spacing: \\[2pt]
    text = text.replace("\\%", "%").replace("\\&", "&").replace("\\$", "$").replace("\\_", "_")
    text = text.replace("\\#", "#").replace("\\\\", " ").replace("~", " ").replace("--", "–")
    text = _ANY_CMD.sub(" ", text)
    text = text.replace("{", " ").replace("}", " ").replace("[", " ").replace("]", " ")
    return re.sub(r"\s+", " ", text).strip()


def item_text(item: Item) -> str:
    return to_plain("\n".join(item.lines))


def digest(doc: Document) -> str:
    """Compact plain-text view of every marked item, for scoring and selection prompts."""
    out: list[str] = []
    for section in doc.sections:
        out.append(f"## {section.name}")
        for child in section.children:
            if isinstance(child, Entry):
                heading = to_plain("\n".join(child.head))
                out.append(f"### [{child.id}] {heading}")
                out.extend(f"- [{it.id}] {item_text(it)}" for it in child.items)
            else:
                out.append(f"- [{child.id}] {item_text(child)}")
    return "\n".join(out)


_PHONE_CANDIDATE = re.compile(r"(?<!\d)\+?\d[\d\s().-]{7,}\d(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def _has_phone(text: str) -> bool:
    """Digit runs of 9+ digits; shorter ones are years and ranges like 2019--2022."""
    return any(sum(c.isdigit() for c in m.group(0)) >= 9 for m in _PHONE_CANDIDATE.finditer(text))


_SENSITIVE = {
    "phone number": _has_phone,
    "email address": lambda text: bool(_EMAIL.search(text)),
}


def sensitive_warnings(doc: Document) -> list[str]:
    """Marked items that look like they contain contact details (these go to the LLM)."""
    warnings = []
    for section in doc.sections:
        for child in section.children:
            texts = (
                [(child.id, "\n".join(child.head))]
                + [(i.id, "\n".join(i.lines)) for i in child.items]
                if isinstance(child, Entry)
                else [(child.id, "\n".join(child.lines))]
            )
            for ident, body in texts:
                for label, check in _SENSITIVE.items():
                    if check(body):
                        warnings.append(f"{ident}: looks like it contains a {label}")
    return warnings


# --- assembly ---------------------------------------------------------------------------------


@dataclass
class Selection:
    """What to keep and in which order. Missing keys mean "keep everything, original order"."""

    sections: dict[str, list[str]] = field(default_factory=dict)  # section -> child ids
    items: dict[str, list[str]] = field(default_factory=dict)  # entry id -> item ids


def _pick[T: (Entry, Item)](children: list[T], wanted: list[str] | None) -> list[T]:
    if wanted is None:
        return list(children)
    by_id = {c.id: c for c in children}
    unknown = [w for w in wanted if w not in by_id]
    if unknown:
        raise CvError(f"unknown ids in selection: {', '.join(unknown)}")
    return [by_id[w] for w in dict.fromkeys(wanted)]


def translation_units(doc: Document) -> dict[str, list[str]]:
    """Translatable text of the CV keyed by id: items, entry heads and section heads."""
    units: dict[str, list[str]] = {}
    for section in doc.sections:
        if any(ln.strip() for ln in section.head):
            units[f"section:{section.name}"] = list(section.head)
        for child in section.children:
            if isinstance(child, Entry):
                units[child.id] = list(child.head)
                for item in child.items:
                    units[item.id] = list(item.lines)
            else:
                units[child.id] = list(child.lines)
    return units


def assemble(
    doc: Document,
    selection: Selection | None = None,
    translation: dict[str, list[str]] | None = None,
) -> str:
    """Rebuild the LaTeX with only the selected entries/items, copying original text verbatim.

    ``translation`` (unit id -> lines, see ``translation_units``) replaces the text of the units
    it contains; structure, markers' content and everything unmarked stay untouched.
    """
    selection = selection or Selection()
    tr = translation or {}
    out: list[str] = []
    for node in doc.nodes:
        if not isinstance(node, Section):
            out.extend(node)
            continue
        chosen = _pick(node.children, selection.sections.get(node.name))
        required = [c.id for c in node.children if isinstance(c, Entry) and c.required]
        missing = [r for r in required if r not in {c.id for c in chosen}]
        if missing:
            raise CvError(f"selection drops required entries: {', '.join(missing)}")
        if node.children and not chosen:
            continue  # nothing left in the section: omit its heading too (avoids empty lists)
        out.extend(tr.get(f"section:{node.name}", node.head))
        for child in chosen:
            if isinstance(child, Entry):
                out.extend(tr.get(child.id, child.head))
                for item in _pick(child.items, selection.items.get(child.id)):
                    out.extend(tr.get(item.id, item.lines))
                    out.extend(item.tail)
                out.extend(child.suffix)
                out.extend(child.tail)
            else:
                out.extend(tr.get(child.id, child.lines))
                out.extend(child.tail)
        out.extend(node.suffix)
    return "\n".join(out) + "\n"


# --- `cv init`: propose markers for a plain LaTeX CV ----------------------------------------


def propose_markers(text: str) -> str:
    """Insert `% jh:` markers around sections and `\\item` bullets of an unmarked CV.

    A starting point for the person to review: sections become selectable and every bullet
    gets an id. Entries (`\\cventry`-style blocks) are not guessed; wrap them by hand.
    """
    lines = text.splitlines()
    out: list[str] = []
    section: str | None = None
    counter = 0
    in_doc = False

    def close() -> None:
        nonlocal section
        if section:
            out.append("% jh:endsection")
            section = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("\\begin{document}"):
            in_doc = True
        if in_doc and (m := re.match(r"\\section\*?\{([^}]*)\}", stripped)):
            close()
            section = _SLUG_RE.sub("-", m.group(1).lower()).strip("-") or "section"
            counter = 0
            out.append(f"% jh:section {section}")
            out.append(line)
            continue
        if in_doc and stripped.startswith("\\end{document}"):
            close()
        if section and stripped.startswith("\\item"):
            counter += 1
            out.append(f"% jh:item {section}-{counter}")
        out.append(line)
    close()
    return "\n".join(out) + "\n"


# --- escaping and compiling -------------------------------------------------------------------

_ESCAPES = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    "—": "---", "–": "--", "“": "``", "”": "''", "‘": "`", "’": "'", "…": r"\ldots{}",
    "\u00a0": "~",
}  # fmt: skip


def escape(text: str) -> str:
    """Escape plain text so it is safe inside LaTeX (used for everything an LLM writes)."""
    return "".join(_ESCAPES.get(ch, ch) for ch in text)


@dataclass
class CompileResult:
    ok: bool
    detail: str
    pdf: bytes | None = None
    pages: int = 0


RESOURCE_SUFFIXES = {
    ".cls",
    ".sty",
    ".bst",
    ".bib",
    ".png",
    ".jpg",
    ".jpeg",
    ".pdf",
    ".ttf",
    ".otf",
}


def compile_pdf(
    tex: str, engine: str, timeout: int, resources: Path | None = None
) -> CompileResult:
    """Compile LaTeX source in a temp dir (shell escape off) and return the PDF and page count.

    ``resources`` is a folder whose class/style/font/image files are copied next to the source,
    so CVs that rely on custom ``.cls``/``.sty`` files or images compile like they do in place.
    """
    import shutil
    import subprocess
    import tempfile

    binary = shutil.which(engine)
    if binary is None:
        return CompileResult(False, f"'{engine}' not found in PATH")
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        if resources is not None and resources.is_dir():
            for extra in resources.iterdir():
                if extra.is_file() and extra.suffix.lower() in RESOURCE_SUFFIXES:
                    shutil.copy(extra, work / extra.name)
        (work / "doc.tex").write_text(tex)
        if engine == "tectonic":
            cmd = [binary, "-X", "compile", "--untrusted", "doc.tex"]
        else:
            cmd = [binary, "-pdf", "-no-shell-escape", "-interaction=nonstopmode", "doc.tex"]
        try:
            proc = subprocess.run(
                cmd, cwd=work, capture_output=True, text=True, timeout=timeout, check=False
            )
        except subprocess.TimeoutExpired:
            return CompileResult(False, f"compilation timed out after {timeout}s")
        pdf_path = work / "doc.pdf"
        if proc.returncode != 0 or not pdf_path.exists():
            tail = (proc.stderr or proc.stdout).strip().splitlines()[-5:]
            return CompileResult(False, "compilation failed: " + " | ".join(tail))
        from pypdf import PdfReader

        data = pdf_path.read_bytes()
        pages = len(PdfReader(str(pdf_path)).pages)
    return CompileResult(True, "compiled OK", data, pages)
