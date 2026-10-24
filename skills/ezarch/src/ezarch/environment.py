"""Versioned, platform-aware runtime discovery and optional local installation."""
from __future__ import annotations

import hashlib
import importlib.metadata
import os
import platform
import plistlib
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

from .project import skill_root, write_json
from .runtime import download, locations, lock, register_tool, registered_tool, require_install_location

BLENDER_VERSION = "4.5.11"
BLENDER_RELEASE = "https://mirror.blender.org/release/Blender4.5/"
BLENDER_FILES = {
    "Darwin-arm64": ("blender-4.5.11-macos-arm64.dmg", "1fad76c7da9451c7d6db99f1a5ed3c0a1a461d0aa07bf2b639e2fb4804ca4f13"),
    "Darwin-x86_64": ("blender-4.5.11-macos-x64.dmg", "d5b0e77ab3baf3cfdf8a80847b3b716ec7448ecd8e299564b7f5a934427224fc"),
    "Windows-AMD64": ("blender-4.5.11-windows-x64.zip", "e11d3a8e4d4249be5a7db4a9325c1f670037d4233467c3b0bda181001efe44d3"),
}


def ensure_supported_platform():
    if platform.system() not in ("Darwin", "Windows"):
        raise RuntimeError("EZarch releases support Windows and macOS only")


def install_font():
    """Install only EZarch's uniquely named open font in the current user's scope."""
    ensure_supported_platform()
    source = skill_root() / "assets/fonts/EZarchFang.ttf"
    folder = (Path.home() / "Library/Fonts" if platform.system() == "Darwin" else
              Path(os.environ["LOCALAPPDATA"]) / "Microsoft/Windows/Fonts")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / source.name
    if target.exists() and target.read_bytes() != source.read_bytes():
        raise RuntimeError(f"A different font already occupies {target}; refusing to replace it")
    if not target.exists():
        shutil.copy2(source, target)
    if platform.system() == "Windows":
        import ctypes
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
            winreg.SetValueEx(key, "EZarch Fang Regular (TrueType)", 0, winreg.REG_SZ, str(target))
        ctypes.windll.gdi32.AddFontResourceW(str(target))
        result = ctypes.c_size_t()
        ctypes.windll.user32.SendMessageTimeoutW(0xffff, 0x001D, 0, 0, 2, 1000, ctypes.byref(result))
    return str(target)


def find_blender() -> str | None:
    candidates = [os.environ.get("EZARCH_BLENDER"), shutil.which("blender"), registered_tool('blender')]
    cache = locations()["tools"]
    candidates += [str(p) for p in (skill_root() / ".ezarch/tools").glob("**/blender.exe")]
    candidates += [str(p) for p in (skill_root() / ".ezarch/tools").glob("**/Blender.app/Contents/MacOS/Blender")]
    candidates += [str(p) for p in cache.glob("**/blender.exe")]
    candidates += [str(p) for p in cache.glob("**/Blender.app/Contents/MacOS/Blender")]
    candidates += ["/Applications/Blender.app/Contents/MacOS/Blender",
                   str(Path.home() / "Applications/Blender.app/Contents/MacOS/Blender")]
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(variable)
        if root:
            candidates += [str(p) for p in Path(root).glob("Blender Foundation/Blender*/blender.exe")]
    for value in candidates:
        if not value or not Path(value).is_file():
            continue
        try:
            first = subprocess.check_output([value, "--version"], text=True, timeout=20).splitlines()[0]
            if first.startswith("Blender ") and tuple(int(v) for v in first.split()[1].split(".")[:2]) >= (4, 5):
                return value
        except (OSError, ValueError, subprocess.SubprocessError):
            continue
    return None


def _install_blender() -> str:
    ensure_supported_platform()
    existing = find_blender()
    if existing:
        return existing
    key = f"{platform.system()}-{platform.machine()}"
    if key not in BLENDER_FILES:
        raise RuntimeError(f"No tested Blender installation profile for {key}")
    filename, expected = BLENDER_FILES[key]
    destination = locations(create=True)["tools"] / f"blender-{BLENDER_VERSION}"
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / filename
    download(BLENDER_RELEASE + filename, archive, sha256=expected)
    if filename.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for member in z.infolist():
                if not (destination / member.filename).resolve().is_relative_to(destination.resolve()):
                    raise RuntimeError("Unsafe archive member")
            z.extractall(destination)
    else:
        attached = subprocess.check_output(["hdiutil", "attach", "-nobrowse", "-readonly", "-plist", str(archive)])
        entries = plistlib.loads(attached)["system-entities"]
        mount = next(Path(v["mount-point"]) for v in entries if "mount-point" in v)
        try:
            app = next(mount.glob("*.app"))
            subprocess.run(["ditto", str(app), str(destination / "Blender.app")], check=True)
        finally:
            subprocess.run(["hdiutil", "detach", str(mount)], check=True)
    executable = find_blender()
    if not executable:
        raise RuntimeError("Blender installed but version probe failed; inspect OS launch authorization")
    return executable


def doctor(out: Path | None = None):
    from .cad import find_oda
    packages = {}
    for name in ("ezarch", "ezdxf", "pymupdf", "resvg-py", "cadquery", "cadquery-ocp", "rhino3dm", "trimesh", "pycollada"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    from . import __version__
    result = {"skill_code": {"version": __version__, "root": str(skill_root())},
              "system": platform.system(), "architecture": platform.machine(),
              "python": platform.python_version(), "blender": find_blender(), "packages": packages,
              "oda_file_converter": find_oda(), "native_apps": "deferred", "ifc": "deferred",
              "locations": {k: str(v) for k, v in locations().items()},
              "operations": [probe_capability(name) for name in ("cad", "pdf", "geometry")]}
    if out:
        write_json(out, result)
    return result


def _install_oda():
    """Fetch the optional proprietary converter from ODA, outside distributable files.

    macOS: copy the signed app into the private tool cache. Windows: administrative
    MSI extraction (no machine-wide registration). Licensing/system prompts, if any,
    are reported rather than bypassed. The official installer is never redistributed.
    """
    import re

    from .cad import find_oda
    ensure_supported_platform()
    existing = find_oda()
    if existing:
        return existing
    page = 'https://www.opendesign.com/guestfiles/oda_file_converter'
    request = urllib.request.Request(page, headers={'User-Agent': 'EZarch'})
    with urllib.request.urlopen(request, timeout=60) as response:
        html = response.read().decode('utf-8')
    suffix = ('macOsX_arm64.*?\\.dmg' if platform.machine() == 'arm64' else 'macOsX_x64.*?\\.dmg') if platform.system() == 'Darwin' else '.*?\\.msi'
    match = re.search(r'ODAFileConverter[^"&<>\s]*?' + suffix, html)
    if not match:
        raise RuntimeError(f'Official ODA download layout changed; inspect {page} for the appropriate installer')
    filename = match.group()
    directory = locations(create=True)['tools'] / 'oda'
    directory.mkdir(parents=True, exist_ok=True)
    archive = directory / Path(filename).name
    url = 'https://www.opendesign.com/guestfiles/get?filename=' + filename
    print(f'Downloading official ODA installer: {archive.name}', flush=True)
    download(url, archive)
    print(f'Downloaded {archive.stat().st_size} bytes; verifying and extracting', flush=True)
    if platform.system() == 'Darwin':
        result = subprocess.check_output(['hdiutil', 'attach', '-nobrowse', '-readonly', '-plist', str(archive)], timeout=180)
        mounts = [e['mount-point'] for e in plistlib.loads(result)['system-entities'] if 'mount-point' in e]
        if not mounts:
            raise RuntimeError('ODA disk image did not mount')
        mount = mounts[0]
        try:
            apps = list(Path(mount).glob('*.app'))
            if len(apps) != 1:
                raise RuntimeError('Unexpected ODA installer contents')
            subprocess.run(['codesign', '--verify', '--deep', '--strict', str(apps[0])], check=True, capture_output=True, timeout=120)
            print('ODA application signature verified; copying application', flush=True)
            shutil.copytree(apps[0], directory / apps[0].name, symlinks=True, dirs_exist_ok=True)
        finally:
            subprocess.run(['hdiutil', 'detach', mount], check=True, capture_output=True, timeout=60)
    else:
        # Installer is obtained over HTTPS directly from the vendor; verify its publisher signature.
        import base64
        script = ('$ErrorActionPreference = "Stop"; $ProgressPreference = "SilentlyContinue"; '
                  '$s = Get-AuthenticodeSignature -LiteralPath $env:EZARCH_ODA_INSTALLER; '
                  '$s | Select-Object Status, StatusMessage | ConvertTo-Json -Compress; '
                  'if ($s.Status -ne "Valid") { exit 1 }')
        encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
        # A PowerShell 7 parent can pass incompatible module paths to Windows PowerShell 5.
        # Let the selected executable initialize its own module search paths.
        verification_env = {k: v for k, v in os.environ.items() if k.upper() != 'PSMODULEPATH'}
        verification_env['EZARCH_ODA_INSTALLER'] = str(archive)
        shell = shutil.which('pwsh') or shutil.which('powershell')
        if not shell:
            raise RuntimeError('PowerShell is needed to verify the ODA Windows installer')
        verification = subprocess.run([shell, '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
            env=verification_env, capture_output=True,
            text=True, errors='replace', timeout=120)
        if verification.returncode:
            raise RuntimeError(f'ODA installer signature validation failed: {(verification.stdout + verification.stderr)[-2000:]}')
        subprocess.run(['msiexec', '/a', str(archive), '/qn', 'TARGETDIR=' + str(directory / 'app')], check=True, timeout=180)
    executable = find_oda()
    if not executable:
        raise RuntimeError(f'ODA extraction completed without a callable converter; inspect {directory}')
    write_json(directory / 'download.json', {'official_page': page, 'installer': archive.name,
                                            'sha256': hashlib.sha256(archive.read_bytes()).hexdigest()})
    return executable


def install_blender():
    require_install_location()
    with lock(locations(create=True)["state"] / "blender-install.lock"):
        path = _install_blender()
        register_tool('blender', path)
        return path


def install_oda():
    require_install_location()
    with lock(locations(create=True)["state"] / "oda-install.lock"):
        path = _install_oda()
        register_tool('oda', path)
        return path


def probe_capability(name):
    """Actual small import/operation probe; no install and no full-disk scan."""
    import sys
    scripts = {
        "cad": "import ezdxf; d=ezdxf.new(); d.modelspace().add_line((0,0),(1,1))",
        "pdf": "import pymupdf; d=pymupdf.open(); d.new_page(); assert d.tobytes()",
        "geometry": "from shapely.geometry import box; assert box(0,0,2,2).area == 4",
        "model": "import trimesh,rhino3dm; assert trimesh.creation.box().vertices.shape[1] == 3",
    }
    if name not in scripts:
        raise ValueError(f"Probe names: {list(scripts)}")
    try:
        call = subprocess.run([sys.executable, "-c", scripts[name]], capture_output=True, text=True, timeout=30)
        return {"capability": name, "state": "ready" if call.returncode == 0 else "failed", "detail": call.stderr[-2000:]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"capability": name, "state": "failed", "detail": str(error)}
