"""Apply public defaults and optional private preferences through Codex's version-checked writer."""
import argparse
import json
import ntpath
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import tempfile
import time
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import config as local_config


PUBLIC_KEYS = ("approval_policy", "sandbox_mode")
OPTIONAL_KEYS = ("model", "model_reasoning_effort")


class Server:
    def __init__(self, executable, home, native_home):
        env = dict(os.environ, CODEX_HOME=native_home)
        windows_launcher = executable.lower().endswith((".exe", ".cmd", ".bat"))
        if os.name != "nt" and windows_launcher:
            entries = [entry for entry in env.get("WSLENV", "").split(":")
                       if entry and entry.split("/")[0] != "CODEX_HOME"]
            env["WSLENV"] = ":".join([*entries, "CODEX_HOME"])
        command = [executable, "app-server"]
        if executable.lower().endswith((".cmd", ".bat")):
            if os.name != "nt":
                try:
                    executable = subprocess.check_output(
                        ["wslpath", "-w", executable], text=True, timeout=10,
                    ).strip()
                except (OSError, subprocess.SubprocessError):
                    raise RuntimeError("Cannot translate the Windows Codex command shim path") from None
            command = ["cmd.exe", "/d", "/c", executable, "app-server"]
        # Config RPCs supply their own cwd. Keep inherited Windows working-directory
        # handles outside the selected home so they do not pin its removal.
        startup_cwd = tempfile.gettempdir() if os.name == "nt" else ("/mnt/c" if windows_launcher else home)
        self.process = subprocess.Popen(
            command, cwd=startup_cwd, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8",
        )
        self.messages = queue.Queue()
        self.serial = 0
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()

    def _read(self):
        try:
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except ValueError:
                    self.messages.put(None)
                    return
        finally:
            self.messages.put(None)

    def call(self, method, params):
        self.serial += 1
        request = {"id": self.serial, "method": method, "params": params}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + 30
        while True:
            try:
                reply = self.messages.get(timeout=max(0, deadline - time.monotonic()))
            except queue.Empty:
                raise RuntimeError("Codex config request timed out: " + method) from None
            if reply is None:
                raise RuntimeError("Codex config server ended; check config syntax and installed runtime")
            if reply.get("id") != self.serial:
                continue
            if "error" in reply:
                code = reply["error"].get("code", "unknown")
                raise RuntimeError("Codex rejected {} ({}); inspect config or managed requirements".format(method, code))
            if "result" not in reply:
                raise RuntimeError("Codex config response has no result: " + method)
            return reply["result"]

    def notify(self, method):
        self.process.stdin.write(json.dumps({"method": method, "params": {}}) + "\n")
        self.process.stdin.flush()

    def close(self):
        self.process.stdin.close()
        forced = False
        status = None
        try:
            # Native RPC teardown can drain for 30 seconds after EOF; do not orphan
            # its process behind a command shim by terminating that shim early.
            status = self.process.wait(timeout=45)
        except subprocess.TimeoutExpired:
            forced = True
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    raise RuntimeError("Codex config server shutdown could not reap the owned process") from None
        self.reader.join(timeout=5)
        if self.reader.is_alive():
            raise RuntimeError("Codex config server shutdown left its stdio reader open")
        self.process.stdout.close()
        if forced:
            raise RuntimeError("Codex config server shutdown required forced termination")
        if status != 0:
            raise RuntimeError("Codex config server shutdown returned a nonzero exit; inspect native configuration/startup")


def compose(tracked, local):
    """Public permission defaults plus optional private model preferences."""
    if set(tracked) != set(PUBLIC_KEYS):
        raise RuntimeError("Invalid tracked Codex defaults: only the permission defaults are public")
    policy = dict(tracked)
    policy.update(local)
    if set(policy) - set(PUBLIC_KEYS) - set(OPTIONAL_KEYS) \
            or not all(isinstance(value, str) and value for value in policy.values()):
        raise RuntimeError("Invalid Codex settings policy")
    return policy


def user_layer(snapshot, target):
    normalize = ntpath.normcase if "\\" in target else os.path.normcase
    layers = [layer for layer in snapshot.get("layers") or []
              if layer.get("name", {}).get("type") == "user"
              and not layer["name"].get("profile")
              and normalize(layer["name"].get("file", "")) == normalize(target)]
    if len(layers) != 1 or not isinstance(layers[0].get("config"), dict) or not layers[0].get("version"):
        raise RuntimeError("Codex did not return one versioned user config layer for the selected home")
    return layers[0]


def configure(server, target, policy, apply):
    read_params = {"includeLayers": True,
                   "cwd": (ntpath if "\\" in target else os.path).dirname(target)}
    snapshot = server.call("config/read", read_params)
    layer = user_layer(snapshot, target)
    existing = layer["config"]
    if "default_permissions" in existing or "sandbox_workspace_write" in existing:
        raise RuntimeError("Codex user config has a permission profile or workspace policy; reconcile it explicitly first")
    changes = {key: value for key, value in policy.items() if existing.get(key) != value}
    if changes:
        if not apply:
            raise RuntimeError("Codex managed settings differ from the composed policy")
        for key, value in changes.items():
            previous = existing.get(key)
            label = previous if isinstance(previous, str) else "unset" if previous is None else "custom value"
            print("Codex setting change: {}: {} -> {}".format(key, label, value), flush=True)
        result = server.call("config/batchWrite", {
            "filePath": layer["name"]["file"], "expectedVersion": layer["version"],
            "edits": [{"keyPath": key, "value": value, "mergeStrategy": "replace"}
                      for key, value in changes.items()],
            "reloadUserConfig": False,
        })
        if result.get("status") != "ok":
            raise RuntimeError("Codex did not confirm an unoverridden config write")
        snapshot = server.call("config/read", read_params)
        projected = user_layer(snapshot, target)["config"]
        if {k: v for k, v in existing.items() if k not in policy} != {k: v for k, v in projected.items() if k not in policy}:
            raise RuntimeError("Codex config verification found an unrelated setting change")
    else:
        projected = existing
    if any(projected.get(key) != value or snapshot.get("config", {}).get(key) != value
           for key, value in policy.items()):
        raise RuntimeError("Codex effective settings differ from the composed policy; inspect higher-priority configuration")
    return bool(changes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("apply", "check"))
    parser.add_argument("home", type=Path)
    parser.add_argument("--codex", required=True)
    parser.add_argument("--native-home")
    args = parser.parse_args()
    tracked = json.loads(Path(__file__).with_name("user-settings.json").read_text())
    _, local = local_config.load()
    policy = compose(tracked, local.get('codex',{}))
    home = args.home.resolve()
    native_home = args.native_home or str(home)
    target = (ntpath if "\\" in native_home else os.path).join(native_home, "config.toml")
    if args.operation == "apply":
        home.mkdir(parents=True, exist_ok=True)
    server = Server(args.codex, home, native_home)
    try:
        server.call("initialize", {"clientInfo": {"name": "agents-sot-config", "version": "1.0"}})
        server.notify("initialized")
        changed = configure(server, target, policy, args.operation == "apply")
    finally:
        server.close()
    print("Codex settings {}: {}".format("applied" if changed else "already current", target))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print("error: " + str(error), file=sys.stderr)
        sys.exit(1)
