"""Generate/verify the exhaustive Gruntz import and divergence ledger."""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
from io import StringIO
from pathlib import Path

from rom1.core.paths import CONFIG, REPO


PIN = "00960e4a9beb6dfbf3f7e604bd5050ef8bf5e078"
LEDGER = CONFIG / "gruntz_parity.tsv"
FIELDS = ("upstream_path", "local_path", "class", "upstream_sha256",
          "local_sha256", "reason", "proof")
SKIP_LOCAL = {"config/gruntz_parity.tsv"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(upstream: str) -> str:
    if upstream.startswith("scripts/gruntz/"):
        return "scripts/rom1/" + upstream.removeprefix("scripts/gruntz/")
    if upstream.startswith("editor/nvim/lua/gruntz/"):
        return "editor/nvim/lua/rom1/" + upstream.removeprefix(
            "editor/nvim/lua/gruntz/")
    if upstream == "editor/nvim/plugin/gruntz.lua":
        return "editor/nvim/plugin/rom1.lua"
    return upstream


def renamed(data: bytes) -> bytes | None:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    for old, new in (("GRUNTZ.EXE", "ALLODS.EXE"),
                     ("Gruntz", "Rom1"), ("GRUNTZ", "ROM1"),
                     ("gruntz", "rom1")):
        text = text.replace(old, new)
    return text.encode()


def local_files() -> set[str]:
    try:
        discovered = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"], cwd=REPO, capture_output=True,
            check=True).stdout
    except subprocess.CalledProcessError as error:
        raise ValueError(f"{REPO}: cannot enumerate repository files") from error
    return {
        path.decode("utf-8")
        for path in discovered.split(b"\0")
        if path and path.decode("utf-8") not in SKIP_LOCAL
    }


def verify_upstream_revision(upstream: Path) -> None:
    """A Git checkout must be exactly the advertised clean pin.

    Source exports without ``.git`` remain supported: their per-file hashes
    are the proof.  A checkout provides stronger evidence, so never let HEAD
    drift while the ledger banner continues to claim ``PIN``.
    """
    if not (upstream / ".git").exists():
        return
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=upstream, capture_output=True,
            text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError as error:
        raise ValueError(f"{upstream}: cannot read Git revision") from error
    if head != PIN:
        raise ValueError(f"{upstream}: HEAD is {head}, expected pinned {PIN}")
    try:
        dirty = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=upstream, capture_output=True, text=True,
            check=True).stdout.splitlines()
    except subprocess.CalledProcessError as error:
        raise ValueError(f"{upstream}: cannot inspect Git cleanliness") from error
    if dirty:
        raise ValueError(f"{upstream}: pinned checkout is dirty ({dirty[0]})")


def generate(upstream: Path) -> list[dict[str, str]]:
    if not (upstream / "scripts/gruntz/cli.py").is_file():
        raise ValueError(f"{upstream}: not the pinned Gruntz tree")
    verify_upstream_revision(upstream)
    rows = []
    claimed = set()
    for source in sorted(path for path in upstream.rglob("*") if path.is_file()
                         and ".git" not in path.parts and "build" not in path.parts
                         and "__pycache__" not in path.parts and path.suffix != ".pyc"):
        up = source.relative_to(upstream).as_posix()
        local = local_path(up)
        destination = REPO / local
        up_hash = sha(source)
        if not destination.is_file():
            klass, local_hash = "excluded", ""
            reason = "Gruntz game source/evidence or adjunct not imported"
            proof = "local path absent"
        else:
            claimed.add(local)
            local_hash = sha(destination)
            if source.read_bytes() == destination.read_bytes():
                klass, reason, proof = "exact", "byte-identical infrastructure", "sha256 equal"
            elif renamed(source.read_bytes()) == destination.read_bytes():
                klass = "rename"
                reason = "mechanical Gruntz-to-RoM1 namespace substitution"
                proof = "canonical token transform"
            elif local.startswith(("config/", "docs/", ".agents/")) \
                    or local in ("README.md", "AGENTS.md"):
                klass = "target"
                reason = "same surface, RoM1 executable evidence/doctrine"
                proof = "tracked local sha256"
            else:
                klass = "seam"
                reason = "reviewed RoM1 compatibility adapter"
                proof = "tracked local sha256 and in-tree tests"
        rows.append(dict(zip(FIELDS, (up, local, klass, up_hash, local_hash,
                                      reason, proof))))

    for local in sorted(local_files() - claimed):
        path = REPO / local
        rows.append(dict(zip(FIELDS, ("-", local, "target", "", sha(path),
            "RoM1-only evidence, adapter, documentation, or vendor input",
            "tracked local sha256"))))
    return rows


def render(rows: list[dict[str, str]]) -> str:
    out = StringIO()
    out.write(f"# gruntz_commit={PIN}\n")
    writer = csv.DictWriter(out, FIELDS, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def read() -> list[dict[str, str]]:
    with LEDGER.open(newline="") as stream:
        return list(csv.DictReader((line for line in stream if not line.startswith("#")),
                                   delimiter="\t"))


def verify(rows: list[dict[str, str]], upstream: Path | None) -> None:
    if upstream is not None:
        verify_upstream_revision(upstream)
    if len({(row["upstream_path"], row["local_path"]) for row in rows}) != len(rows):
        raise ValueError("duplicate parity row")
    covered = set()
    for row in rows:
        local = row["local_path"]
        destination = REPO / local
        if row["class"] == "excluded":
            if destination.exists():
                raise ValueError(f"excluded path exists: {local}")
        else:
            if not destination.is_file():
                raise ValueError(f"ledger local path missing: {local}")
            actual = sha(destination)
            if actual != row["local_sha256"]:
                raise ValueError(f"local drift: {local}: {actual}")
            covered.add(local)
        if upstream is not None and row["upstream_path"] != "-":
            source = upstream / row["upstream_path"]
            if not source.is_file() or sha(source) != row["upstream_sha256"]:
                raise ValueError(f"upstream drift: {row['upstream_path']}")
            if row["class"] == "exact" and source.read_bytes() != destination.read_bytes():
                raise ValueError(f"exact mapping differs: {local}")
            if row["class"] == "rename" and renamed(source.read_bytes()) != destination.read_bytes():
                raise ValueError(f"rename mapping differs: {local}")
    missing = local_files() - covered
    if missing:
        raise ValueError("unclassified local files: " + ", ".join(sorted(missing)[:12]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path,
                        help=f"checkout/export at Gruntz commit {PIN}")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.write:
            if args.upstream is None:
                parser.error("--write requires --upstream")
            rows = generate(args.upstream)
            LEDGER.parent.mkdir(parents=True, exist_ok=True)
            LEDGER.write_text(render(rows))
        rows = read()
        verify(rows, args.upstream)
    except (OSError, ValueError) as error:
        print(f"[parity] FAIL: {error}")
        return 1
    counts = {name: sum(row["class"] == name for row in rows)
              for name in ("exact", "rename", "target", "seam", "excluded")}
    print(f"[parity] exact: {len(rows)} rows; " + ", ".join(
          f"{key}={value}" for key, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
