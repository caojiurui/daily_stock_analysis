from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path


SUPPORTED_REPOS = {
    "https://github.com/ZhuLinsen/alphasift.git": {
        "archive": "https://codeload.github.com/ZhuLinsen/alphasift/zip/{rev}",
    }
}
DEFAULT_VERSION = "git version 2.54.0.windows.1"
STATE_FILE = ".git-shim-state.json"
EMPTY_REV = "0" * 40


def eprint(*parts: object) -> None:
    print(*parts, file=sys.stderr)


def load_state(repo_root: Path) -> dict:
    path = repo_root / STATE_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(repo_root: Path, state: dict) -> None:
    path = repo_root / STATE_FILE
    path.write_text(json.dumps(state, ensure_ascii=True, indent=2), encoding="utf-8")


def strip_options(args: list[str]) -> list[str]:
    return [arg for arg in args if not arg.startswith("-")]


def resolve_repo_root(cwd: Path) -> Path:
    for candidate in (cwd, *cwd.parents):
        if (candidate / STATE_FILE).exists():
            return candidate
    return cwd


def ensure_supported_repo(repo_url: str) -> dict:
    normalized = repo_url.strip()
    if normalized in SUPPORTED_REPOS:
        return SUPPORTED_REPOS[normalized]
    raise SystemExit(f"git-shim only supports {', '.join(SUPPORTED_REPOS)}; got: {repo_url}")


def clean_repo_checkout(repo_root: Path) -> None:
    for child in repo_root.iterdir():
        if child.name in {STATE_FILE, ".git"}:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def copy_tree_contents(source_root: Path, target_root: Path) -> None:
    for child in source_root.iterdir():
        target = target_root / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            shutil.copy2(child, target)


def download_archive(repo_url: str, rev: str, target_root: Path) -> None:
    repo_cfg = ensure_supported_repo(repo_url)
    archive_url = repo_cfg["archive"].format(rev=rev)

    with tempfile.TemporaryDirectory(prefix="git-shim-") as tmpdir:
        tmp_path = Path(tmpdir)
        zip_path = tmp_path / "repo.zip"
        with urllib.request.urlopen(archive_url, timeout=60) as response:
            zip_path.write_bytes(response.read())

        extract_root = tmp_path / "extract"
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_root)

        extracted_dirs = [path for path in extract_root.iterdir() if path.is_dir()]
        if len(extracted_dirs) != 1:
            raise SystemExit(f"unexpected archive layout for {archive_url}")

        clean_repo_checkout(target_root)
        copy_tree_contents(extracted_dirs[0], target_root)


def cmd_version() -> int:
    print(DEFAULT_VERSION)
    return 0


def cmd_clone(args: list[str]) -> int:
    nonopts = strip_options(args)
    if len(nonopts) < 3:
        eprint("git-shim clone: expected repo URL and target path")
        return 2

    repo_url = nonopts[-2]
    target = Path(nonopts[-1]).resolve()
    ensure_supported_repo(repo_url)
    target.mkdir(parents=True, exist_ok=True)
    (target / ".git").mkdir(exist_ok=True)
    save_state(target, {"repo_url": repo_url, "current_rev": EMPTY_REV})
    return 0


def _extract_revision(args: list[str]) -> str:
    nonopts = strip_options(args)
    for candidate in reversed(nonopts[1:]):
        if re.fullmatch(r"[0-9a-fA-F]{7,40}", candidate):
            return candidate.lower()
    return ""


def cmd_checkout(args: list[str], repo_root: Path) -> int:
    state = load_state(repo_root)
    repo_url = state.get("repo_url")
    if not repo_url:
        eprint("git-shim checkout: missing repo_url state")
        return 2

    rev = _extract_revision(args)
    if not rev:
        eprint("git-shim checkout: missing revision")
        return 2

    download_archive(repo_url, rev, repo_root)
    state["current_rev"] = rev
    save_state(repo_root, state)
    return 0


def cmd_reset(args: list[str], repo_root: Path) -> int:
    return cmd_checkout(["checkout", *args[1:]], repo_root)


def cmd_rev_parse(args: list[str], repo_root: Path) -> int:
    state = load_state(repo_root)
    current_rev = state.get("current_rev") or EMPTY_REV

    if "--git-dir" in args:
        print(str(repo_root / ".git"))
        return 0

    if "--show-toplevel" in args:
        print(str(repo_root))
        return 0

    target = args[-1] if len(args) > 1 else "HEAD"
    if target in {"HEAD", "HEAD^0"}:
        print(current_rev)
        return 0

    print(target)
    return 0


def cmd_show_ref(args: list[str], repo_root: Path) -> int:
    state = load_state(repo_root)
    current_rev = state.get("current_rev") or EMPTY_REV
    rev = _extract_revision(args) or current_rev
    print(f"{rev} refs/shim/{rev}")
    return 0


def cmd_submodule(args: list[str], repo_root: Path) -> int:
    return 0


def cmd_fetch(args: list[str], repo_root: Path) -> int:
    return 0


def cmd_config(args: list[str], repo_root: Path) -> int:
    state = load_state(repo_root)
    repo_url = state.get("repo_url", "")
    if args[-1] == "remote.origin.url":
        print(repo_url)
        return 0
    if "--get-regexp" in args:
        print(f"remote.origin.url {repo_url}")
        return 0
    return 0


def cmd_symbolic_ref(args: list[str], repo_root: Path) -> int:
    return 1


def main(argv: list[str]) -> int:
    if len(argv) <= 1:
        return 0

    command = argv[1]
    args = argv[1:]
    repo_root = resolve_repo_root(Path.cwd())

    if command == "version":
        return cmd_version()
    if command == "clone":
        return cmd_clone(args)
    if command == "checkout":
        return cmd_checkout(args, repo_root)
    if command == "reset":
        return cmd_reset(args, repo_root)
    if command == "rev-parse":
        return cmd_rev_parse(args, repo_root)
    if command == "show-ref":
        return cmd_show_ref(args, repo_root)
    if command == "submodule":
        return cmd_submodule(args, repo_root)
    if command == "fetch":
        return cmd_fetch(args, repo_root)
    if command == "config":
        return cmd_config(args, repo_root)
    if command == "symbolic-ref":
        return cmd_symbolic_ref(args, repo_root)

    eprint(f"git-shim does not implement command: {' '.join(args)}")
    return 2


def console_main() -> int:
    return main(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
