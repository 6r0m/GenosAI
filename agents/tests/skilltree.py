"""Shared discovery and parsing for the skill-system tests.

One place owns how a skill, a document, a link, and an owner are recognised, so the
tests below disagree about findings, never about definitions.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.abspath(os.path.join(HERE, os.pardir))
SKILLS = os.path.join(AGENTS, "skills")
SHARED = os.path.join(SKILLS, ".shared")
TEMPLATES = os.path.join(SHARED, "templates")
REPO = os.path.abspath(os.path.join(AGENTS, os.pardir))

# Vendored/generated trees are not ours to audit, so they are never router nodes.
NOT_OURS = re.compile(
    r"(^|/)(\.git|node_modules|__pycache__|\.pytest_cache|tmp|\.toolchain"
    r"|vendor|third[-_]party|playwright-cli|synced|\.trash)(/|$)"
)

# A fenced block or inline code holds examples and template placeholders, not links.
_FENCE = re.compile(r"^(`{3,4}).*?^\1\s*$", re.S | re.M)
_INLINE = re.compile(r"`[^`\n]*`")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def strip_code(text):
    return _INLINE.sub("", _FENCE.sub("", text))


def frontmatter(text):
    """(dict, body) for a SKILL.md, or (None, text) when there is no frontmatter.

    Block scalars (`description: >-`) are folded into their value. Without this the
    parser returned the indicator itself, so a length check on such a description
    measured two characters and passed no matter what the description said.
    """
    if not text.startswith("---\n"):
        return None, text
    head, _, body = text[4:].partition("\n---\n")
    fm = {}
    lines = head.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        i += 1
        if not line or line[0].isspace() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value in (">", ">-", ">+", "|", "|-", "|+"):
            folded, literal = [], value[0] == "|"
            while i < len(lines) and (not lines[i].strip() or lines[i][0].isspace()):
                folded.append(lines[i].strip())
                i += 1
            value = ("\n" if literal else " ").join(p for p in folded if p)
        fm[key.strip()] = value
    return fm, body


def skills():
    """(name, path, frontmatter, body) for every registered skill."""
    for name in sorted(os.listdir(SKILLS)):
        path = os.path.join(SKILLS, name, "SKILL.md")
        if os.path.isfile(path):
            fm, body = frontmatter(read(path))
            yield name, path, fm, body


def markdown_files(root, include_templates=True):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not NOT_OURS.search(os.path.relpath(os.path.join(base, d), root).replace(os.sep, "/"))]
        for f in files:
            if not f.endswith(".md"):
                continue
            path = os.path.join(base, f)
            if not include_templates and _is_template(path):
                continue
            yield path


def _is_template(path):
    return os.path.abspath(path).startswith(TEMPLATES + os.sep)


def links(path):
    """Relative markdown links in a file, code blocks excluded.

    Inline `../shared.md` references count too: the skills reference `.shared/` that
    way by convention, and a broken one breaks the skill.
    """
    text = read(path)
    found = [m for m in re.findall(r"\]\(([^)h#][^)]*\.md)\)", strip_code(text))]
    found += re.findall(r"`(\.\./[^`]*\.md)`", text)
    return found


def router_nodes(root):
    """Directories we maintain that carry their own README.md.

    This is the mechanically detectable half of ownership, and all a test may claim to
    have found. Architectural ownership is semantic — a directory owns a responsibility
    — and its README is how that ownership is declared and reached. So every router node
    here is checkable for reachability; a real owner that never declared itself is
    invisible to this function by construction, and no test may claim otherwise.
    """
    found = set()
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if not NOT_OURS.search(os.path.relpath(os.path.join(base, d), root).replace(os.sep, "/"))]
        norm = os.path.normpath(base)
        if "README.md" in files and not NOT_OURS.search(os.path.relpath(norm, root).replace(os.sep, "/")):
            found.add(norm)
    return found


def routes(node_set):
    """{target: [routers]} for routes only.

    A route is a link from a router into its own directory; a link pointing anywhere
    else is a citation, which is unrestricted.
    """
    table = {}
    for owner in node_set:
        body = strip_code(read(os.path.join(owner, "README.md")))
        for target in re.findall(r"\]\(([^)#][^)]*?)\)", body):
            if target.startswith(("http", "mailto")):
                continue
            resolved = os.path.normpath(os.path.join(owner, target))
            if resolved.endswith("README.md"):
                resolved = os.path.dirname(resolved)
            if resolved not in node_set or resolved == owner:
                continue
            if resolved.startswith(owner + os.sep):
                table.setdefault(resolved, []).append(owner)
    return table
