"""Standard-library runtime locations and recoverable dependency preparation."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def config_file():
    if os.environ.get("EZARCH_CONFIG"):
        return Path(os.environ["EZARCH_CONFIG"]).expanduser().resolve()
    base = (Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) if os.name == "nt"
            else Path.home() / "Library/Application Support")
    return base / "EZarch/settings.json"


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def locations(home=None, *, create=False):
    config = read_json(config_file(), {})
    selected = home or os.environ.get("EZARCH_HOME") or config.get("home")
    root = Path(selected).expanduser().resolve() if selected else config_file().parent / "runtime"
    result = {"home": root, **{name: root / name for name in ("tools", "envs", "cache", "temp", "state")}}
    if create:
        for path in result.values():
            path.mkdir(parents=True, exist_ok=True)
        probe = root / (".write-test-" + uuid.uuid4().hex)
        probe.write_bytes(b"")
        probe.unlink()
    return result


def configure(home):
    paths = locations(home, create=True)
    value = read_json(config_file(), {})
    value["home"] = str(paths["home"])
    atomic_json(config_file(), value)
    return {k: str(v) for k, v in paths.items()}


def require_install_location(home=None):
    if os.name == 'nt' and not (home or os.environ.get('EZARCH_HOME') or read_json(config_file(), {}).get('home')):
        raise ValueError('Choose a runtime directory before installation; pass home or set EZARCH_HOME. No download started.')


def register_tool(name, path):
    if name not in {'oda', 'blender', 'uv'}:
        raise ValueError('Tool names: oda, blender, uv')
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    state = locations(create=True)['state'] / 'tools.json'
    with lock(state.with_suffix('.lock')):
        records = read_json(state, {})
        records[name] = {'path': str(path), 'state': 'registered_path', 'registered_at': time.time()}
        atomic_json(state, records)
    return records[name]


def registered_tool(name):
    record = read_json(locations()['state'] / 'tools.json', {}).get(name, {})
    path = Path(record['path']) if record.get('path') else None
    return str(path) if path and path.is_file() else None


def process_env(home=None):
    paths = locations(home, create=True)
    env = os.environ.copy()
    env.update(EZARCH_HOME=str(paths["home"]), UV_CACHE_DIR=str(paths["cache"] / "uv"),
               UV_PYTHON_INSTALL_DIR=str(paths["home"] / "runtimes/python"),
               UV_TOOL_DIR=str(paths["tools"] / "uv-tools"),
               TMPDIR=str(paths["temp"]), TMP=str(paths["temp"]), TEMP=str(paths["temp"]))
    return env


@contextlib.contextmanager
def lock(path):
    """Fail visibly on concurrent work; never guess whether another process is stale."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as error:
        raise RuntimeError(f"Operation already locked: {path}; inspect its PID before removing a stale lock") from error
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        path.unlink(missing_ok=True)


def download(url, target, *, sha256=None, attempts=3, timeout=20):
    """Verified cache reuse; incomplete bytes never replace a valid destination."""
    target = Path(target)
    if sha256 and target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == sha256:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with lock(target.with_suffix(target.suffix + ".lock")):
        partial = target.with_suffix(target.suffix + ".part")
        try:
            for attempt in range(attempts):
                try:
                    request = urllib.request.Request(url, headers={"User-Agent": "EZarch"})
                    with urllib.request.urlopen(request, timeout=timeout) as response, partial.open("wb") as output:
                        shutil.copyfileobj(response, output)
                    break
                except (urllib.error.URLError, TimeoutError):
                    if attempt + 1 == attempts:
                        raise
                    time.sleep(min(2 ** attempt, 4))
            else:
                raise ValueError("attempts must be positive")
            if sha256 and hashlib.sha256(partial.read_bytes()).hexdigest() != sha256:
                raise ValueError(f"Download checksum mismatch: {url}")
            os.replace(partial, target)
        finally:
            partial.unlink(missing_ok=True)
    return target


def python_at(environment):
    return Path(environment) / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def binding_file(skill, home=None):
    key = hashlib.sha256(str(Path(skill).resolve()).encode()).hexdigest()[:24]
    return locations(home)["state"] / f"runtime-{key}.json"


def dependency_fingerprint(skill):
    raw = (Path(skill) / 'uv.lock').read_bytes()
    try:
        value = tomllib.loads(raw.decode())
        for package in value.get('package', []):
            if package.get('name') == 'ezarch' and package.get('source', {}).get('editable') == '.':
                package['version'] = 'workspace-code-loaded-separately'
        raw = json.dumps(value, sort_keys=True).encode()
    except tomllib.TOMLDecodeError:
        pass  # uv itself reports invalid lock files; preserve identity for diagnostics.
    return hashlib.sha256(raw).hexdigest()


def find_python(skill, home=None):
    record = read_json(binding_file(skill, home), {})
    selected = Path(record["python"]) if record.get("python") else None
    if record.get("lock_sha256") and record["lock_sha256"] != dependency_fingerprint(skill):
        return None
    if selected and selected.is_file():
        return selected
    legacy = python_at(Path(skill) / ".venv")
    return legacy if legacy.is_file() else None


def prepare(skill, *, extras=(), home=None, uv=None):
    """Share locked dependencies; load each installation's code from its own src."""
    skill = Path(skill).resolve()
    require_install_location(home)
    if set(extras) - {"model", "dev"}:
        raise ValueError("Runtime extras: model, dev")
    paths = locations(home, create=True)
    uv = uv or registered_tool("uv") or shutil.which("uv") or str(paths["tools"] / ("uv.exe" if os.name == "nt" else "uv"))
    payload = dependency_fingerprint(skill).encode() + json.dumps([sorted(extras), platform.system(), platform.machine(), "3.12"]).encode()
    key = hashlib.sha256(payload).hexdigest()[:24]
    environment = paths["envs"] / key
    python = python_at(environment)
    ready = paths["state"] / f"environment-{key}.json"
    with lock(paths["state"] / f"environment-{key}.lock"):
        reused = ready.exists() and python.exists()
        try:
            if not reused:
                if shutil.disk_usage(paths["home"]).free < 512 * 1024 ** 2:
                    raise OSError("Less than 512 MiB free; choose another runtime directory")
                env = process_env(home)
                env["UV_PROJECT_ENVIRONMENT"] = str(environment)
                command = [str(uv), "sync", "--project", str(skill), "--python", "3.12", "--frozen",
                           "--no-install-project"]
                for extra in sorted(extras):
                    command += ["--extra", extra]
                subprocess.run(command, env=env, check=True)
            subprocess.run([str(python), "-c", "import ezdxf,pymupdf,shapely,yaml; d=ezdxf.new(); d.modelspace().add_line((0,0),(1,1))"],
                           check=True, timeout=30)
            atomic_json(ready, {"python": str(python), "extras": sorted(extras), "key": key})
            record = {"python": str(python), "extras": sorted(extras), "key": key, "reused": reused,
                      "lock_sha256": dependency_fingerprint(skill)}
            atomic_json(binding_file(skill, home), record)
            return record
        except Exception as error:
            atomic_json(paths["state"] / f"failed-{key}.json",
                        {"error": str(error), "environment": str(environment), "previous_binding_preserved": True})
            if reused:
                ready.unlink(missing_ok=True)
            raise


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("status")
    s = sub.add_parser("configure")
    s.add_argument("home")
    s = sub.add_parser('register-tool')
    s.add_argument('name', choices=['oda', 'blender', 'uv'])
    s.add_argument('path')
    a = parser.parse_args(argv)
    if a.operation == 'register-tool':
        result = register_tool(a.name, a.path)
    else:
        result = configure(a.home) if a.operation == "configure" else {k: str(v) for k, v in locations().items()}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
