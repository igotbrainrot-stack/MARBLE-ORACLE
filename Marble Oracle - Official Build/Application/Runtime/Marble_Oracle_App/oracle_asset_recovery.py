"""Restore large, content-addressed distribution assets from GitHub-friendly parts.

A regular dev ZIP already includes the complete files, so this is a no-op for
users of the ZIP. A repository checkout may contain pieces under data/_packed/
instead: these are joined atomically and SHA-256 verified before the application
loads its optional media. No network, pip modules or elevated rights required.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import tempfile

PART_SIZE = 900_000
# (file size in bytes, SHA256, number of 900,000-byte parts)
LARGE_ARCHIVES = {
    "data/photo_bezel_locked.zip": (6520800, "da962b4f535a4f4a93fdbfd20dcfdfe0bffa6048def61ce6b788b8f751ca677a", 8),
    "data/photo_bezel_source.png": (1084738, "2ef042847cf1655ad2939d9086fbfeefc965f4e42c90b1ae74a96fd3b82ed584", 2),
    "data/photo_bezel.zip": (8790196, "e0eddd20826581eb315310d8663eebfa2db4588585807cd4cd18d0ac06d8a5d5", 10),
    "data/latin_voices.zip": (5_535_134, "4503c3aeffc07117015034a14bf45e2e3f7cc8fa5f2d08bc638f8772115953d2", 7),
    "data/tarot_cards.zip": (5_669_018, "a086f1a7bd6f638284e0e36fe345c8b1a67d3ea6791d8dce6823f8258cbcb50d", 7),
}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(131072), b""):
            digest.update(block)
    return digest.hexdigest()


def restore_one(root: Path, relative_path: str, size: int, sha256: str,
                part_count: int) -> bool:
    """True when the verified archive exists, else raise on a failed restore.

    Existing good data is never rewritten. No partial, invalid or unchecked
    output is exposed at the destination; failed staging is removed.
    """
    root = Path(root).resolve()
    target = root / relative_path
    if target.is_file() and target.stat().st_size == size and _digest(target) == sha256:
        return True
    name = target.name
    parts = [root / "data" / "_packed" / (name + ".part%03d" % i)
             for i in range(part_count)]
    if not all(p.is_file() for p in parts):
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent,
                                         prefix=".restore-", suffix=".tmp",
                                         delete=False) as output:
            staged = Path(output.name)
            actual_hash = hashlib.sha256()
            actual_size = 0
            for index, part in enumerate(parts):
                with part.open("rb") as source:
                    while True:
                        block = source.read(131072)
                        if not block:
                            break
                        actual_hash.update(block)
                        actual_size += len(block)
                        if actual_size > size:
                            raise ValueError("oversized archive part " + str(part))
                        output.write(block)
        if actual_size != size or actual_hash.hexdigest() != sha256:
            raise ValueError("checksum mismatch when restoring " + relative_path)
        os.replace(staged, target)
        return True
    finally:
        if staged is not None:
            try:
                staged.unlink(missing_ok=True)
            except OSError:
                pass


def restore_missing_assets(root: str | Path | None = None) -> list[str]:
    """Restore missing archives if GitHub's split chunks are present.

    Return paths that could not be restored. The application treats absent
    optional media the same way as in prior builds (fail-soft).
    """
    root = Path(root or Path(__file__).resolve().parent)
    if not (root / "data" / "_packed").is_dir():
        # No parts to join, so nothing can be restored: skip hashing ~18 MB at every start.
        return [p for p, (size, _, _) in LARGE_ARCHIVES.items()
                if not ((root / p).is_file() and (root / p).stat().st_size == size)]
    missing = []
    for relative_path, (size, sha, count) in LARGE_ARCHIVES.items():
        try:
            if not restore_one(root, relative_path, size, sha, count):
                missing.append(relative_path)
        except (OSError, ValueError):
            missing.append(relative_path)
    return missing
