from __future__ import annotations

import json
from typing import Optional

import src.citations as citations
import src.db as db


def _fmt_workspace_items(workspace_id: int, user_id: int, style: str = "apa") -> list[str]:
    items = db.get_workspace_items(user_id, workspace_id) or []
    formatted = []
    for item in items:
        c = citations.format_citation(
            title=item.get("title", ""),
            source=item.get("source_name", ""),
            url=item.get("source_url", ""),
            style=style,
            author=item.get("authors") or item.get("author"),
            year=item.get("year"),
        )
        formatted.append(c)
    return formatted


def export_to_markdown(
    workspace_id: int,
    user_id: int,
    include_notes: bool = True,
    include_sources: bool = True,
    citation_style: str = "apa",
) -> str:
    workspace = db.get_workspace(user_id, workspace_id)
    name = workspace["name"] if workspace else "Workspace"
    lines = [f"# {name}", ""]
    if include_sources:
        lines.append("## Sources")
        lines.append("")
        for c in _fmt_workspace_items(workspace_id, user_id, citation_style):
            lines.append(f"- {c}")
        lines.append("")
    if include_notes:
        notes = db.get_workspace_notes(workspace_id, user_id) or []
        if notes:
            lines.append("## Notes")
            lines.append("")
            for note in notes:
                lines.append(f"### {note.get('title', 'Untitled')}")
                lines.append("")
                content = note.get("content", "")
                if content:
                    import re
                    content_text = re.sub(r"<[^>]+>", "", content)
                    lines.append(content_text)
                lines.append("")
    return "\n".join(lines)


def export_to_latex(workspace_id: int, user_id: int, citation_style: str = "apa") -> str:
    workspace = db.get_workspace(user_id, workspace_id)
    name = workspace["name"] if workspace else "Workspace"
    lines = [
        r"\documentclass{article}",
        r"\title{" + name + "}",
        r"\date{}",
        r"\begin{document}",
        r"\maketitle",
        "",
        r"\section*{Sources}",
        "",
    ]
    for i, c in enumerate(_fmt_workspace_items(workspace_id, user_id, citation_style), 1):
        lines.append(r"\bibitem{" + str(i) + "} " + c)
        lines.append("")
    notes = db.get_workspace_notes(workspace_id, user_id) or []
    if notes:
        lines.append(r"\section*{Notes}")
        lines.append("")
        for note in notes:
            lines.append(r"\subsection*{" + note.get("title", "Untitled") + "}")
            lines.append("")
            content = note.get("content", "")
            if content:
                import re
                content_text = re.sub(r"<[^>]+>", "", content)
                lines.append(content_text)
            lines.append("")
    lines.append(r"\end{document}")
    return "\n".join(lines)


def export_to_bibtex(workspace_id: int, user_id: int) -> str:
    items = db.get_workspace_items(user_id, workspace_id) or []
    entries = []
    for i, item in enumerate(items, 1):
        cite_key = f"source{i}"
        title = item.get("title", "")
        authors = item.get("authors", "") or item.get("author", "")
        year = item.get("year") or "n.d."
        journal = item.get("journal", "")
        volume = item.get("volume", "")
        issue = item.get("issue", "")
        doi = item.get("doi", "")
        source_url = item.get("source_url", "")
        source_name = item.get("source_name", "")
        if journal:
            entry_type = "article"
            fields = [
                f"  title = {{{title}}}",
                f"  author = {{{authors}}}",
                f"  journal = {{{journal}}}",
                f"  year = {{{year}}}",
            ]
            if volume:
                fields.append(f"  volume = {{{volume}}}")
            if issue:
                fields.append(f"  number = {{{issue}}}")
            if doi:
                fields.append(f"  doi = {{{doi}}}")
            if source_url and not doi:
                fields.append(f"  url = {{{source_url}}}")
        elif source_name:
            entry_type = "book"
            fields = [
                f"  title = {{{title}}}",
                f"  author = {{{authors}}}",
                f"  publisher = {{{source_name}}}",
                f"  year = {{{year}}}",
            ]
            if source_url:
                fields.append(f"  url = {{{source_url}}}")
        else:
            entry_type = "misc"
            fields = [
                f"  title = {{{title}}}",
                f"  year = {{{year}}}",
            ]
            if authors:
                fields.append(f"  author = {{{authors}}}")
            if source_url:
                fields.append(f"  url = {{{source_url}}}")
        entry = f"@{entry_type}{{{cite_key},\n" + ",\n".join(fields) + "\n}"
        entries.append(entry)
    return "\n\n".join(entries) + "\n"


def export_to_epub_html(workspace_id: int, user_id: int, citation_style: str = "apa") -> str:
    workspace = db.get_workspace(user_id, workspace_id)
    name = workspace["name"] if workspace else "Workspace"
    lines = [
        "<!DOCTYPE html>",
        '<html xmlns="http://www.w3.org/1999/xhtml">',
        "<head>",
        f"  <title>{name}</title>",
        '  <meta charset="utf-8"/>',
        "</head>",
        "<body>",
        f"  <h1>{name}</h1>",
        "",
        "  <h2>Sources</h2>",
        '  <ul class="sources">',
    ]
    for c in _fmt_workspace_items(workspace_id, user_id, citation_style):
        lines.append(f"    <li>{c}</li>")
    lines.append("  </ul>")
    lines.append("")
    notes = db.get_workspace_notes(workspace_id, user_id) or []
    if notes:
        lines.append("  <h2>Notes</h2>")
        for note in notes:
            lines.append(f"  <h3>{note.get('title', 'Untitled')}</h3>")
            content = note.get("content", "")
            if content:
                lines.append(f"  <div class=\"note-content\">{content}</div>")
            lines.append("")
    lines.append("</body>")
    lines.append("</html>")
    return "\n".join(lines)


BUILTIN_TEMPLATES = {
    "default": "{{content}}",
    "school-essay": """---
title: {{title}}
student: {{student_name}}
class: {{class}}
date: {{date}}
---

{{content}}

## References

{{citations}}""",
    "lab-report": """---
title: {{title}}
student: {{student_name}}
class: {{class}}
date: {{date}}
---

## Objective

{{objective}}

## Materials & Methods

{{methods}}

## Results

{{results}}

## Discussion

{{discussion}}

## References

{{citations}}""",
}


def apply_export_template(content: str, template_name: str, metadata: dict) -> str:
    template_str = BUILTIN_TEMPLATES.get(template_name)
    if template_str is None:
        template_str = BUILTIN_TEMPLATES["default"]
    result = template_str.replace("{{content}}", content)
    for key, value in metadata.items():
        placeholder = "{{" + key + "}}"
        result = result.replace(placeholder, str(value) if value is not None else "")
    return result
