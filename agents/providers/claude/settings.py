#!/usr/bin/env python3
"""Compose, plan, confirm and apply Claude Code settings to each side's settings.json.

    settings.py check [--side NAME PATH]... [--tracked FILE]
    settings.py validate [--tracked FILE]
    settings.py apply [--side NAME PATH]... [--approve PLAN_ID] [--tracked FILE]
    settings.py hook  [--tracked FILE]
    settings.py registered-hook [--settings FILE]

The tracked file's top-level keys are owned and replaced with their composed values. Every other key in a live file belongs to
Claude Code or to that side, and is kept with its position. Claude Code writes the same file, so nothing is
written without a plan the operator saw: `apply` asks in a terminal, and otherwise needs `--approve` with the
id of that exact plan. The id binds source/local inputs, projection code and generated paths, and every
side's name, path and raw content. A changed input or native save makes approval stale.

Exit codes: 0 clean or applied; 1 differs (check) or a side failed to write (apply); 2 could not check;
3 not approved.

`hook` is the session-start drift check: one line on stdout, `clean` or a JSON `systemMessage` naming the
differing keys, never their values. session-check.sh turns anything else into a warning.

`registered-hook` runs the session-start warning a live file registers, the way Claude Code does, and judges
it: clean only on exit 0 with no output within its timeout. selfcheck.sh uses it.

Standard library only; it runs under WSL Python and Windows Python alike.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

# Importing the guard-posture checker must not leave a __pycache__ inside the agents tree it checks.
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.realpath(__file__))
AGENTS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, AGENTS)
import config as local_config
TRACKED = os.path.join(HERE, "user-settings.json")
CHECKER = os.path.join(HERE, os.pardir, os.pardir, "permissions", "check-registration.py")
ADAPTER = "providers/claude/session-check.sh"
HOOK_TIMEOUT = 5

# The registered session-start template, by structure: run the managed adapter and
# print a fixed systemMessage when it cannot run. Mentioning the adapter is not enough, because a command
# that only echoes text would put that text into every session's context.
SESSION_HOOK = re.compile(
    re.escape('bash "@AGENTS_ROOT@/' + ADAPTER + '" || ') +
    r"printf '%s\\n' '(?P<fallback>\{[^']*\})'")

CLEAN, DIFFERS, CANNOT, REFUSED = 0, 1, 2, 3
ABSENT = object()

# A leaf whose name looks like a credential, or that holds a free-form command line, is never printed:
# the plan reaches terminals, logs and agent transcripts. Everything under `env` is treated the same.
CREDENTIAL = re.compile(r"(?i)key|token|secret|passw|credential|auth|cookie|session|bearer|jwt")


class Refusal(Exception):
    """An input that cannot be trusted enough to plan from. Nothing is written."""


class Side:
    def __init__(self, name, path, raw, live, tracked):
        self.name, self.path, self.raw, self.live = name, path, raw, live
        self.desired = render_hooks(tracked, name)
        tracked = self.desired
        if raw is None:
            self.lines = []
            self.changes = len(tracked)
        else:
            self.lines = [line for key, value in tracked.items()
                          for line in diff(live.get(key, ABSENT), value, (key,))]
            self.changes = len(self.lines)
        self.unowned = [key for key in live if key not in tracked]


def canonical(value):
    return "\0absent" if value is ABSENT else json.dumps(value, sort_keys=True, ensure_ascii=False)


def same(a, b):
    """Equal as JSON. Python's == would treat `true` and `1` as the same setting."""
    return canonical(a) == canonical(b)


def sensitive(path):
    if len(path) > 1 and path[0] == "env":
        return True
    names = [part for part in path if isinstance(part, str)]
    if not names:
        return False
    leaf = names[-1]
    return bool(CREDENTIAL.search(leaf)) or leaf == "command" or leaf.endswith("Helper")


def render(value, path):
    if value is ABSENT:
        return "(absent)"
    if isinstance(value, dict):
        return "{" + ", ".join("%s: %s" % (json.dumps(k, ensure_ascii=False), render(v, path + (k,)))
                               for k, v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ", ".join(render(v, path + (i,)) for i, v in enumerate(value)) + "]"
    if sensitive(path):
        return "<redacted #%s>" % hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()[:8]
    return json.dumps(value, ensure_ascii=False)


def dotted(path):
    return ".".join(str(part) for part in path)


def diff(old, new, path):
    """One plan line per changed leaf; a list changes per element."""
    if same(old, new):
        return []
    if isinstance(old, dict) and isinstance(new, dict):
        lines = []
        for key in list(old) + [k for k in new if k not in old]:
            lines += diff(old.get(key, ABSENT), new.get(key, ABSENT), path + (key,))
        return lines
    if isinstance(old, list) and isinstance(new, list):
        olds, news = [canonical(v) for v in old], [canonical(v) for v in new]
        lines = ["%s: − %s" % (dotted(path), render(v, path + (i,)))
                 for i, v in enumerate(old) if olds[i] not in news]
        lines += ["%s: + %s" % (dotted(path), render(v, path + (i,)))
                  for i, v in enumerate(new) if news[i] not in olds]
        return lines or ["%s: reordered" % dotted(path)]
    return ["%s: %s → %s" % (dotted(path), render(old, path), render(new, path))]


def parse(raw, label):
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise Refusal("%s: not valid JSON (%s)" % (label, exc))
    if not isinstance(value, dict):
        raise Refusal("%s: not a JSON object" % label)
    return value


def read(path, label):
    """Raw bytes, or None for a file that does not exist yet. Anything else unreadable refuses."""
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise Refusal("%s: cannot read %s (%s)" % (label, path, exc.strerror or exc))


def preflight(path):
    """The tracked file, refused unless it keeps the guard posture and the session-start warning."""
    raw = read(path, "tracked file")
    if raw is None:
        raise Refusal("tracked file: %s does not exist" % path)
    tracked = parse(raw, "tracked file")
    spec = importlib.util.spec_from_file_location("check_registration", CHECKER)
    if spec is None or not os.path.isfile(CHECKER):
        raise Refusal("guard posture checker missing: %s" % CHECKER)
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    problems = checker.check(path)
    if problems:
        raise Refusal("tracked file fails the guard posture:\n  " + "\n  ".join(problems))
    hooks = [h for e in tracked.get("hooks", {}).get("SessionStart", []) if isinstance(e, dict)
             for h in e.get("hooks", []) if isinstance(h, dict)]
    # The tracked file owns the whole `hooks` value and installs it on both sides, so any other SessionStart
    # command would run in every session there, and its plain stdout could reach the model.
    if len(hooks) > 1:
        raise Refusal("tracked file: SessionStart must hold exactly one hook, the drift warning (found %d)"
                      % len(hooks))
    found = [(h, SESSION_HOOK.fullmatch(h.get("command", "")))
             for h in hooks if isinstance(h.get("command"), str)]
    found = [(h, m) for h, m in found if m]
    if not found:
        raise Refusal('tracked file: no SessionStart hook has the expected command '
                      '(managed source path and the || printf systemMessage fallback)')
    for hook, match in found:
        try:
            fallback = json.loads(match.group("fallback"))
        except ValueError:
            fallback = None
        if not (isinstance(fallback, dict) and list(fallback) == ["systemMessage"]
                and isinstance(fallback["systemMessage"], str) and fallback["systemMessage"]):
            raise Refusal("tracked file: the SessionStart fallback must print one JSON systemMessage")
        timeout = hook.get("timeout")
        if hook.get("type") != "command" or isinstance(timeout, bool) \
                or not isinstance(timeout, (int, float)) or not 0 < timeout <= HOOK_TIMEOUT:
            raise Refusal("tracked file: the SessionStart warning needs type command and a timeout of at "
                          "most %d s" % HOOK_TIMEOUT)
    try:
        local_raw, local = local_config.load()
        tracked = local_config.compose(tracked, local.get("claude", {}))
    except local_config.ConfigError as exc:
        raise Refusal(str(exc)) from None
    types=parse(read(os.path.join(HERE,'local-settings.types.json'),'local settings types'), 'local settings types')
    for key,value in tracked.items():
        if value is not None and type(value).__name__ != types.get(key):
            raise Refusal('local Claude setting has an invalid type')
    tracked={key:value for key,value in tracked.items() if value is not None}
    problems = checker.check_settings(tracked, "composed settings")
    if problems:
        raise Refusal("local settings fail the required guard posture")
    # The plan also binds the local file, source location, and projection code.
    sources = [raw.hex(), None if local_raw is None else local_raw.hex(), AGENTS]
    for source in (__file__, local_config.__file__, os.path.join(HERE,'local-settings.types.json')):
        content = read(source, "settings source")
        if content is None:
            raise Refusal("settings projection source is missing")
        sources.append(content.hex())
    return canonical(sources).encode("utf-8"), tracked


def render_hooks(tracked, side):
    root = AGENTS.replace("\\", "/")
    if side == "windows" and os.name != "nt":
        try:
            proc = subprocess.run(["wslpath", "-w", AGENTS], capture_output=True, text=True,
                                  encoding="utf-8", timeout=5, check=True)
        except (OSError, subprocess.SubprocessError):
            raise Refusal("cannot resolve the Windows source path") from None
        root = proc.stdout.strip().replace("\\", "/")
        if not root:
            raise Refusal("Windows source path is empty")
    desired = json.loads(json.dumps(tracked))
    for groups in desired.get("hooks", {}).values():
        for group in groups:
            for hook in group.get("hooks", []):
                if isinstance(hook.get("command"), str):
                    hook["command"] = re.sub(r'"@AGENTS_ROOT@/([^"\n]+)"',
                                             lambda m: shlex.quote(root + "/" + m[1]), hook["command"])
    return desired


def load(sides, tracked):
    out = []
    for name, path in sides:
        raw = read(path, name)
        out.append(Side(name, path, raw, {} if raw is None else parse(raw, name), tracked))
    return out


def plan_id(tracked_raw, sides):
    digest = hashlib.sha256(tracked_raw)
    for side in sides:
        for part in (side.name, os.path.realpath(side.path)):
            digest.update(b"\0" + part.encode("utf-8"))
        digest.update(b"\0" + (b"<absent>" if side.raw is None else side.raw))
        digest.update(b"\0" + canonical(side.desired).encode("utf-8"))
    return digest.hexdigest()[:12]


def show(sides, tracked, pid):
    for side in sides:
        print("== Claude settings · %s (%s)" % (side.name, side.path))
        if side.raw is None:
            print("  file absent: will be created with the %d owned keys" % len(tracked))
        elif not side.lines:
            print("  no changes")
        for line in side.lines:
            print("  " + line)
        if side.unowned:
            print("  unowned, kept as they are: " + ", ".join(side.unowned))
    print("plan id: " + pid)
    sys.stdout.flush()


def write(side):
    """Replace the owned keys in the content just re-read, atomically; return the backup path or None."""
    tracked = side.desired
    merged = dict(side.live)
    merged.update(tracked)
    text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
    folder = os.path.dirname(os.path.abspath(side.path))
    os.makedirs(folder, exist_ok=True)
    backup = None
    if side.raw is not None:
        stamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
        backup, n = "%s.%s.bak" % (side.path, stamp), 1
        while os.path.exists(backup):
            backup, n = "%s.%s-%d.bak" % (side.path, stamp, n), n + 1
        # Owner-only whatever the umask: the copy holds everything the live file held, `env` values included.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        with os.fdopen(os.open(backup, flags, 0o600), "wb") as fh:
            fh.write(side.raw)
    fd, temp = tempfile.mkstemp(dir=folder, prefix=".settings.json.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        if side.raw is not None:
            try:
                shutil.copymode(side.path, temp)
            except OSError as exc:
                print("note: %s: could not copy the file mode (%s)" % (side.name, exc), file=sys.stderr)
        os.replace(temp, side.path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise
    landed = parse(read(side.path, side.name) or b"", side.name)
    wrong = [key for key, value in tracked.items() if not same(landed.get(key, ABSENT), value)]
    if wrong:
        raise Refusal("%s: the re-read after writing differs in %s" % (side.name, ", ".join(wrong)))
    return backup


def check(args):
    try:
        tracked_raw, tracked = preflight(args.tracked)
        sides = load(args.side, tracked)
    except Refusal as exc:
        print("could not check: %s" % exc, file=sys.stderr)
        return CANNOT
    show(sides, tracked, plan_id(tracked_raw, sides))
    return DIFFERS if any(side.changes for side in sides) else CLEAN


def validate(args):
    try:
        preflight(args.tracked)
    except Refusal as exc:
        print("invalid Claude configuration: %s" % exc, file=sys.stderr)
        return CANNOT
    return CLEAN


def apply(args):
    try:
        tracked_raw, tracked = preflight(args.tracked)
        sides = load(args.side, tracked)
    except Refusal as exc:
        print("not applied: %s" % exc, file=sys.stderr)
        return CANNOT
    pid = plan_id(tracked_raw, sides)
    show(sides, tracked, pid)
    if not any(side.changes for side in sides):
        print("no changes")
        return CLEAN
    if args.approve:
        if args.approve != pid:
            print("not applied: plan %s was approved, but the settings changed since that plan was shown; "
                  "the current plan is above with id %s" % (args.approve, pid), file=sys.stderr)
            return REFUSED
    else:
        # Windows reports NUL as a terminal, so an immediate end of input also means there is none.
        answer = ""
        if sys.stdin is not None and sys.stdin.isatty():
            sys.stdout.write("Apply these changes? [y/N] ")
            sys.stdout.flush()
            answer = sys.stdin.readline()
        if not answer:
            print("not applied: no terminal to confirm in; review the plan above and pass --approve %s" % pid,
                  file=sys.stderr)
            return REFUSED
        if answer.strip().lower() not in ("y", "yes"):
            print("not applied: declined")
            return REFUSED

    # The operator may have taken minutes over the plan, and Claude Code saves this file itself.
    try:
        fresh_raw, fresh_tracked = preflight(args.tracked)
        fresh = load(args.side, fresh_tracked)
    except Refusal as exc:
        print("not applied: %s" % exc, file=sys.stderr)
        return CANNOT
    if plan_id(fresh_raw, fresh) != pid:
        print("not applied: settings changed since the plan was shown; run again to review the new plan",
              file=sys.stderr)
        return REFUSED

    applied = []
    for side in fresh:
        if not side.changes:
            continue
        try:
            backup = write(side)
        except (OSError, Refusal) as exc:
            pending = [s.name for s in fresh if s.changes and s.name not in applied]
            print("applied: %s; not applied: %s (%s)" % (", ".join(applied) or "none", ", ".join(pending), exc),
                  file=sys.stderr)
            return DIFFERS
        applied.append(side.name)
        print("applied %d changes to %s; backup %s" % (side.changes, side.name, backup or "none"))
    return CLEAN


def own_settings():
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return os.path.join(home, "settings.json")


def hook(args):
    target = own_settings()
    try:
        _, tracked = preflight(args.tracked)
        side = load([("this side", target)], tracked)[0]
    except Refusal as exc:
        return warn("Claude settings drift check could not run: %s" % str(exc).splitlines()[0])
    except Exception as exc:  # reported, never read as clean
        return warn("Claude settings drift check could not run: %s" % type(exc).__name__)
    if side.raw is None:
        return warn("Claude settings: %s is missing, so the tracked settings are not applied here." % target)
    keys = [key for key, value in side.desired.items() if not same(side.live.get(key, ABSENT), value)]
    if not keys:
        print("clean")
        return CLEAN
    return warn("Claude settings here differ from the tracked file in: %s. "
                "install.sh --provider claude shows the plan." % ", ".join(keys))


def warn(message):
    print(json.dumps({"systemMessage": message}))
    return CLEAN


def registered_hook(args):
    path = args.settings or own_settings()
    try:
        raw = read(path, "settings")
        if raw is None:
            raise Refusal("%s does not exist" % path)
        live = parse(raw, path)
    except Refusal as exc:
        print("*** cannot judge the session-start warning: %s" % exc)
        return CANNOT
    hooks = [h for e in live.get("hooks", {}).get("SessionStart", []) if isinstance(e, dict)
             for h in e.get("hooks", []) if isinstance(h, dict) and "session-check.sh" in str(h.get("command"))]
    if not hooks:
        print("*** not registered in %s" % path)
        return CANNOT
    bash = shutil.which("bash")
    if not bash:
        print("*** cannot judge the session-start warning: no bash on PATH")
        return CANNOT
    for entry in hooks:
        # Claude Code's own default when a hook names no timeout.
        limit = entry.get("timeout", 60)
        started = time.monotonic()
        try:
            proc = subprocess.run([bash, "-c", entry["command"]], input="{}", capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=limit + 5)
        except subprocess.TimeoutExpired:
            print("*** still running past its %s s timeout; Claude Code would kill it without a word" % limit)
            return DIFFERS
        elapsed = time.monotonic() - started
        if elapsed > limit:
            print("*** took %.1f s, past its %s s timeout; Claude Code would kill it without a word"
                  % (elapsed, limit))
            return DIFFERS
        if proc.returncode != 0:
            print("*** exit %d, stdout %r" % (proc.returncode, proc.stdout.strip()))
            return DIFFERS
        if proc.stdout.strip():
            print("*** %s" % proc.stdout.strip())
            return DIFFERS
    print("clean: exit 0, no output, %.2f s" % elapsed)
    return CLEAN


def main(argv):
    # Windows Python writes a pipe in the console code page, which has no → or −; the plan would crash there.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("operation", choices=("validate", "check", "apply", "hook", "registered-hook"))
    parser.add_argument("--side", nargs=2, action="append", default=[], metavar=("NAME", "PATH"))
    parser.add_argument("--approve", metavar="PLAN_ID")
    parser.add_argument("--tracked", default=TRACKED)
    parser.add_argument("--settings", metavar="FILE")
    args = parser.parse_args(argv)
    if args.operation in ("check", "apply") and not args.side:
        parser.error("%s needs at least one --side NAME PATH" % args.operation)
    operations = {"validate": validate, "check": check, "apply": apply, "hook": hook, "registered-hook": registered_hook}
    return operations[args.operation](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
