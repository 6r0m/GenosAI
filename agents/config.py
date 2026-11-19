"""Read the AI checkout's private deltas without printing their values."""
import copy
import json
import ntpath
import re
import sys
import argparse
import subprocess
from pathlib import Path

sys.dont_write_bytecode = True
from permissions.guards._paths import native, resolve, too_broad


LOCAL = Path(__file__).resolve().parent.parent / "config.local.json"


class ConfigError(Exception):
    """Invalid local input; consumers must refuse rather than widen permissions."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError("duplicate local configuration key")
        result[key] = value
    return result


def _fields(value, allowed, label):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ConfigError("invalid or unsupported %s fields" % label)


def load():
    try:
        raw = LOCAL.read_bytes()
    except FileNotFoundError:
        # A dangling link is an unreadable configured input, not an absent input.
        if LOCAL.is_symlink():
            raise ConfigError("local configuration link has no target")
        return None, {}
    except OSError:
        raise ConfigError("cannot read local configuration") from None
    try:
        value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_object)
    except (UnicodeError, ValueError):
        raise ConfigError("local configuration is not valid JSON") from None
    _fields(value, ("browser", "permissions", "claude", "codex", "pi"), "local configuration")
    browser = value.get("browser", {})
    _fields(browser, ("cdp_url", "agent_profile", "launcher", "auth"), "browser")
    for key in ("cdp_url", "launcher"):
        if key in browser and browser[key] is not None and not isinstance(browser[key], str):
            raise ConfigError("invalid browser connection field type")
    if "agent_profile" in browser:
        _platform_paths(browser["agent_profile"])
    auth = browser.get("auth", {})
    _fields(auth, ("cookies_dir", "importer", "staging_dir"), "browser auth")
    for path in auth.values():
        _platform_paths(path)
    permissions = value.get("permissions", {})
    _fields(permissions, ("extra_write_roots",), "permissions")
    roots = permissions.get("extra_write_roots", [])
    if not isinstance(roots, list):
        raise ConfigError("extra_write_roots must be an array of absolute paths")
    for root in roots:
        if not isinstance(root, str) or not root or "\0" in root or not (
                root.startswith("/") or (ntpath.splitdrive(root)[0] and ntpath.isabs(root))):
            raise ConfigError("extra_write_roots must contain absolute paths")
        normalized = resolve(native(root))
        key = normalized.replace("\\", "/").rstrip("/").lower()
        drive, tail = ntpath.splitdrive(key)
        parts = key.split("/")
        protected = any(part == ".claude" and parts[index + 1:index + 2] != ["projects"]
                        for index, part in enumerate(parts))
        if too_broad(normalized) or (drive and not tail) or re.fullmatch(r"/[a-z]", key) \
                or key in ("/home", "/users") \
                or re.fullmatch(r"(?:[a-z]:|/[a-z])/users(?:/[^/]+)?|/" + r"home/[^/]+", key) \
                or protected:
            raise ConfigError("extra_write_roots contains an overly broad or protected root")
    claude = value.get("claude", {})
    if not isinstance(claude, dict) or "hooks" in claude:
        raise ConfigError("local Claude settings cannot replace managed hooks")
    codex=value.get('codex', {})
    _fields(codex, ('approval_policy','sandbox_mode'), 'Codex')
    if 'approval_policy' in codex and codex['approval_policy'] not in ('untrusted','on-failure','on-request','never'):
        raise ConfigError('invalid Codex approval policy')
    if 'sandbox_mode' in codex and codex['sandbox_mode'] not in ('read-only','workspace-write','danger-full-access'):
        raise ConfigError('invalid Codex sandbox mode')
    pi=value.get('pi', {})
    _fields(pi, ('active','profiles','secret_root','ownership_root'), 'Pi')
    if pi.get('active') is not None and not isinstance(pi['active'],str):
        raise ConfigError('invalid Pi selection')
    if not isinstance(pi.get('profiles',{}),dict): raise ConfigError('invalid Pi profiles')
    for key in ('secret_root','ownership_root'):
        if key in pi and (not isinstance(pi[key],str) or not pi[key]): raise ConfigError('invalid Pi path')
    return raw, value


def _platform_paths(value):
    if isinstance(value, str) and value:
        return
    if not isinstance(value, dict) or not value or set(value) - {"win", "wsl", "linux"} \
            or any(not isinstance(path, str) or not path for path in value.values()):
        raise ConfigError("invalid browser path reference")


def compose(defaults, overrides, path=()):
    """Known keys merge recursively; permission rules append, other lists replace."""
    if isinstance(defaults, dict):
        if path in (('env',),('enabledPlugins',),('extraKnownMarketplaces',),('pluginConfigs',),('modelSettings',)):
            if not isinstance(overrides,dict): raise ConfigError('invalid local settings map')
            result=copy.deepcopy(defaults);result.update(copy.deepcopy(overrides));return result
        if not isinstance(overrides, dict) or set(overrides) - set(defaults):
            raise ConfigError("unknown local Claude setting or invalid object type")
        result = copy.deepcopy(defaults)
        for key, value in overrides.items():
            result[key] = compose(defaults[key], value, path + (key,))
        return result
    if defaults is None:
        return copy.deepcopy(overrides)
    if type(defaults) is not type(overrides):
        raise ConfigError("local Claude setting has an invalid type")
    if isinstance(defaults, list):
        if path in (("permissions", "allow"), ("permissions", "deny"), ("permissions", "ask")):
            if any(not isinstance(item, str) for item in overrides):
                raise ConfigError("local permission rules must be strings")
            return list(dict.fromkeys(defaults + overrides))
    return copy.deepcopy(overrides)


def pi_input(platform='host', removing=False):
    try: _,local=load()
    except ConfigError:
        if not removing: raise
        print('Pi removal: invalid local input ignored; only canonical source ownership is accepted.',file=sys.stderr)
        local={}
    defaults={'active':None,'profiles':{}} if removing else json.loads((Path(__file__).resolve().parent/'providers/pi/runtime/profiles.json').read_text())
    pi={**defaults,**local.get('pi',{})}
    root=LOCAL.parent
    def portable(value):
        try:
            if sys.platform=='win32':
                mounted=re.match(r'^/(?:mnt/)?([a-zA-Z])(?:/|$)(.*)',value)
                if mounted: return ntpath.normpath(mounted[1].upper()+':/'+mounted[2])
                if value.startswith('/'):
                    raise ConfigError('Linux-only Pi paths need an explicit Windows-accessible location')
                if ntpath.splitdrive(value)[0]:
                    if not ntpath.isabs(value): raise ConfigError('Pi drive paths must be absolute')
                    return ntpath.normpath(value)
                return ntpath.normpath(ntpath.join(str(root),value))
            if ntpath.splitdrive(value)[0]:
                if not ntpath.isabs(value): raise ConfigError('Pi drive paths must be absolute')
                value=subprocess.check_output(['wslpath','-u',value],text=True,timeout=5).strip()
                if not value.startswith('/'): raise ConfigError('cannot resolve the Pi path')
            source=Path(value)
            if not source.is_absolute(): source=root/source
            text=str(source)
            if platform=='windows':
                text=subprocess.check_output(['wslpath','-w',text],text=True,timeout=5).strip()
                if not ntpath.isabs(text): raise ConfigError('cannot resolve the native Pi path')
            return text
        except (OSError,subprocess.SubprocessError):
            raise ConfigError('cannot resolve the Pi input path for this platform') from None
    return {'configured':pi.get('active') is not None, 'root':portable(pi.get('ownership_root',str(root))),
            'secretRoot':portable(pi.get('secret_root',str(root/'secrets'))),
            'profiles':{'active':pi.get('active'),'profiles':pi.get('profiles',{})}}

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',nargs='?',choices=('validate','pi','pi-uninstall'),default='validate')
    parser.add_argument('--platform',choices=('host','wsl','windows'),default='host')
    args=parser.parse_args()
    try:
        if args.operation in ('pi','pi-uninstall'): print(json.dumps(pi_input(args.platform,removing=args.operation=='pi-uninstall')))
        else: load()
    except ConfigError as exc:
        print("invalid local configuration: %s" % exc, file=sys.stderr)
        sys.exit(2)
