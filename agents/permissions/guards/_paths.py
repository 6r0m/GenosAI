"""Paths shared by the guards: how a spelling resolves, which repo a session
works in, and where its transient files belong.

One owner, because getting this wrong is silent in both directions: too little
resolution lets a symlink launder a target, too much rewrites a path that was
never meant for this interpreter and denies something legitimate.
"""
import os
import re
import subprocess
import tempfile

# Git Bash spells C:\\ as /c/. Windows Python does not know that: it treats the
# leading slash as "root of the current drive", so /c/Users/x resolves to
# E:\\c\\Users\\x when the session happens to run from E:. The guard then saw a
# path under no allowed root and refused an in-repo delete. Translate first.
_GITBASH_DRIVE = re.compile(r"^/([A-Za-z])(/|$)")


def native(path):
    """Spell a Git Bash /c/... path the way this interpreter reads paths."""
    if os.name != "nt":
        return path
    match = _GITBASH_DRIVE.match(path)
    if match:
        return "%s:/%s" % (match.group(1).upper(), path[match.end():])
    # Git Bash also mounts /tmp at the Windows temp directory. Left alone it
    # would be joined against the session drive and land on E:/tmp, matching no
    # allowed root - repo_guard refused writes to /tmp on Windows for this.
    if path == "/tmp" or path.startswith("/tmp/"):
        return os.path.join(tempfile.gettempdir(), path[5:]).replace("\\", "/")
    return path


def resolve(path):
    """Follow symlinks, but only when this spelling is native to this platform.

    ``native()`` above has already put a Git Bash drive path into this
    interpreter's spelling. What remains is everything else that is not native
    here - a WSL ``/home/...`` path handed to Windows Python, say. Resolving
    those would rewrite them against the current drive and match no allowed
    root, so they are left exactly as spelled.

    So: walk up to the longest ancestor that actually exists as spelled. If only
    the filesystem root exists, the spelling belongs to another platform and the
    path is returned untouched. Otherwise resolve that ancestor - which follows
    any symlink in it - and re-attach the remainder. Resolving an ancestor
    rather than the full path is also what makes this work for a file that does
    not exist yet, the normal case for a Write.
    """
    path = native(path)
    probe = path
    while probe and not os.path.lexists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            return path                     # nothing along it exists here
        probe = parent
    if not probe or probe == os.path.dirname(probe):
        return path                         # only the root: foreign spelling
    try:
        resolved = os.path.realpath(probe)
    except OSError:
        return path
    return resolved + path[len(probe):]


def repo_root(cwd):
    """The working repo: the project dir Claude Code reports, else the cwd.

    None when that folder is too broad to be one repo. A session started in a
    home folder or at a drive root would otherwise put the whole home or drive
    "inside the repo", and every delete under it in scope.
    """
    root = resolve(os.path.normpath(native(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)))
    return None if too_broad(root) else root


# WSL spellings of the mount point above every drive, a drive, its Users
# folder, and a Windows profile in it.
_WSL_BROAD = re.compile(r"^/mnt(/[a-z](/users(/[^/]+)?)?)?$")


def too_broad(path):
    """A filesystem or drive root, the home folder, or a folder above it."""
    key = _key(path)
    if os.path.dirname(path) == path or _WSL_BROAD.match(key):
        return True
    home = _key(resolve(os.path.normpath(os.path.expanduser("~"))))
    return key == home or home.startswith(key + "/")


def _key(path):
    """One spelling for comparing paths: forward slashes, OS case folding."""
    return os.path.normcase(path).replace("\\", "/").rstrip("/").lower() or "/"


def next_step(payload, repo, subject):
    """How a refused agent carries on, spelled so it can act on it directly.

    It names one place that already exists and is meant for transient files:
    the repo's tmp/ when git ignores it, else the session scratchpad Claude
    Code reports, else none. The guards run in every repository, so naming a
    tmp/ that is missing or tracked would plant a stray directory there.
    """
    where = ignored_repo_tmp(repo)
    scratch = payload.get("scratchpad_dir")
    if where is None and isinstance(scratch, str) and scratch:
        where = "%s (session scratch)" % scratch.replace("\\", "/")
    first = ("Use %s for transient files, or take another approach." % where
             if where else "Take an approach that needs no temporary file.")
    return first + (" If this exact %s is essential to the task, report it as a "
                    "blocker rather than working around this refusal." % subject)


def ignored_repo_tmp(repo):
    """`<repo>/tmp/` when it exists and git ignores it, else None."""
    if repo is None or not os.path.isdir(os.path.join(repo, "tmp")):
        return None
    try:
        ignored = subprocess.run(
            ["git", "-C", repo, "check-ignore", "-q", "tmp/transient"],
            capture_output=True, timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return None
    return repo.replace("\\", "/").rstrip("/") + "/tmp/" if ignored else None
