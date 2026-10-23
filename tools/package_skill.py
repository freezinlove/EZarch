"""Package only declared release files, including from a GitHub source archive."""
import argparse
import hashlib
import json
import re
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath


def release_files(skill: Path, manifest: Path) -> list[tuple[str, Path]]:
    """Resolve an explicit allowlist without following file/directory links."""
    skill = skill.resolve()
    files = []
    seen = set()
    for line in manifest.read_text(encoding="utf-8").splitlines():
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        relative = PurePosixPath(name)
        if (relative.is_absolute() or relative.as_posix() != name
                or any(part in {".", ".."} for part in relative.parts)
                or "\\" in name or ":" in name):
            raise ValueError(f"Unsafe release path: {name}")
        if name.casefold() in seen:
            raise ValueError(f"Duplicate release path: {name}")
        seen.add(name.casefold())
        path = skill
        for part in relative.parts:
            path = path / part
            if path.is_symlink() or path.is_junction():
                raise ValueError(f"Release files cannot use symlinks or junctions: {name}")
        if not path.is_file() or not path.resolve().is_relative_to(skill):
            raise ValueError(f"Missing or invalid release file: {name}")
        files.append((name, path))
    if not files:
        raise ValueError("Release file list is empty")
    return sorted(files)


def package(skill: Path, manifest: Path, out: Path) -> tuple[Path, int, str]:
    files = release_files(skill, manifest)
    # Read metadata from the already validated files, not an unlisted/linked path.
    project = dict(files).get("pyproject.toml")
    if project is None:
        raise ValueError("Release file list must include pyproject.toml")
    version = tomllib.loads(project.read_text(encoding="utf-8"))["project"]["version"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+-]*", version):
        raise ValueError("Invalid release version")
    out.mkdir(parents=True, exist_ok=True)
    archive = out / f"ezarch-{version}-skill.zip"
    marker = {"version": version, "files": {name: hashlib.sha256(file.read_bytes()).hexdigest() for name, file in files}}
    with tempfile.NamedTemporaryFile(dir=out, suffix=".zip.tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for name, file in files:
                # Stable timestamps/permissions make an identical source package reproducible.
                info = zipfile.ZipInfo(f"ezarch/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, file.read_bytes())
            info = zipfile.ZipInfo("ezarch/.ezarch-release.json", date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            z.writestr(info, json.dumps(marker, sort_keys=True).encode())
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")
    return archive, len(files) + 1, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--base-url", help="HTTPS directory serving the versioned release ZIP")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    archive, count, digest = package(root / "skills/ezarch", root / "tools/skill-files.txt", args.out)
    if args.base_url:
        if not args.base_url.startswith("https://"):
            parser.error("Release base URL must use HTTPS")
        version = tomllib.loads((root / "skills/ezarch/pyproject.toml").read_text())["project"]["version"]
        (args.out / "ezarch-release.json").write_text(json.dumps({"version": version, "url": args.base_url.rstrip("/") + "/" + archive.name, "sha256": digest}, indent=2))
    print(f"{archive}: {count} files, SHA256 {digest}")


if __name__ == "__main__":
    main()
