#!/usr/bin/env python3
"""
Skills Sync -- manifest-based seeding and updating of bundled skills.

Copies bundled skills from the repo's skills/ directory into ~/.hermes/skills/
and uses a manifest to track which skills have been synced and their origin hash.

Manifest format (v2): each line is "skill_name:origin_hash" where origin_hash
is the MD5 of the bundled skill at the time it was last synced to the user dir.
Old v1 manifests (plain names without hashes) are auto-migrated.

Update logic:
  - New skills: copied to user dir, origin hash recorded only after success.
  - Existing skills: updated only when the user's copy still matches the
    previously synced bundled hash.
  - User-modified skills: never overwritten.
  - User-deleted skills: respected, not re-added.
  - Bundled skills removed upstream: cleaned from the manifest.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


HERMES_HOME = Path(os.getenv("HERMES_HOME", Path.home() / ".hermes"))
SKILLS_DIR = HERMES_HOME / "skills"
MANIFEST_FILE = SKILLS_DIR / ".bundled_manifest"


def _get_bundled_dir() -> Path:
    """Locate the bundled skills directory in the repo."""
    return Path(__file__).parent.parent / "skills"


def _read_manifest() -> Dict[str, str]:
    """
    Read the manifest as {skill_name: origin_hash}.

    Supports both:
    - v1: plain name per line
    - v2: name:hash per line
    """
    if not MANIFEST_FILE.exists():
        return {}

    try:
        result: Dict[str, str] = {}
        for line in MANIFEST_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                name, _, hash_value = line.partition(":")
                result[name.strip()] = hash_value.strip()
            else:
                result[line] = ""
        return result
    except (OSError, IOError):
        return {}


def _write_manifest(entries: Dict[str, str]) -> None:
    """Write the manifest in v2 name:hash format."""
    MANIFEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{name}:{hash_value}" for name, hash_value in sorted(entries.items())]
    MANIFEST_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _discover_bundled_skills(bundled_dir: Path) -> List[Tuple[str, Path]]:
    """
    Find all bundled SKILL.md files.

    Returns:
        List of (skill_name, skill_directory_path)
    """
    skills: List[Tuple[str, Path]] = []
    if not bundled_dir.exists():
        return skills

    for skill_md in bundled_dir.rglob("SKILL.md"):
        parts = skill_md.parts
        if ".git" in parts or ".github" in parts or ".hub" in parts:
            continue
        skill_dir = skill_md.parent
        skills.append((skill_dir.name, skill_dir))

    return skills


def _compute_relative_dest(skill_dir: Path, bundled_dir: Path) -> Path:
    """
    Preserve category structure under ~/.hermes/skills/.

    Example:
        repo/skills/mlops/axolotl -> ~/.hermes/skills/mlops/axolotl
    """
    return SKILLS_DIR / skill_dir.relative_to(bundled_dir)


def _dir_hash(directory: Path) -> str:
    """Hash all files in a directory for change detection."""
    hasher = hashlib.md5()
    try:
        for file_path in sorted(directory.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(directory)
            hasher.update(str(rel).encode("utf-8"))
            hasher.update(file_path.read_bytes())
    except (OSError, IOError):
        pass
    return hasher.hexdigest()


def sync_skills(quiet: bool = False) -> dict:
    """
    Sync bundled skills into ~/.hermes/skills/ using a hash-aware manifest.

    Returns:
        dict with keys:
          copied, updated, skipped, user_modified, cleaned, total_bundled
    """
    bundled_dir = _get_bundled_dir()
    if not bundled_dir.exists():
        return {
            "copied": [],
            "updated": [],
            "skipped": 0,
            "user_modified": [],
            "cleaned": [],
            "total_bundled": 0,
        }

    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest()
    bundled_skills = _discover_bundled_skills(bundled_dir)
    bundled_names = {name for name, _ in bundled_skills}

    copied: List[str] = []
    updated: List[str] = []
    user_modified: List[str] = []
    skipped = 0

    for skill_name, skill_src in bundled_skills:
        dest = _compute_relative_dest(skill_src, bundled_dir)
        bundled_hash = _dir_hash(skill_src)

        if skill_name not in manifest:
            try:
                if dest.exists():
                    skipped += 1
                    manifest[skill_name] = bundled_hash
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(skill_src, dest)
                    copied.append(skill_name)
                    manifest[skill_name] = bundled_hash
                    if not quiet:
                        print(f"  + {skill_name}")
            except (OSError, IOError) as e:
                if not quiet:
                    print(f"  ! Failed to copy {skill_name}: {e}")
                # Do not write manifest entry on failed copy so the next sync retries.
            continue

        if not dest.exists():
            # Respect user deletions: keep manifest entry, skip re-adding.
            skipped += 1
            continue

        origin_hash = manifest.get(skill_name, "")
        user_hash = _dir_hash(dest)

        if not origin_hash:
            # Migrate old manifest entries by baselining from the user's current copy.
            manifest[skill_name] = user_hash
            skipped += 1
            continue

        if user_hash != origin_hash:
            user_modified.append(skill_name)
            if not quiet:
                print(f"  ~ {skill_name} (user-modified, skipping)")
            continue

        if bundled_hash == origin_hash:
            skipped += 1
            continue

        backup = dest.with_suffix(".bak")
        try:
            if backup.exists():
                shutil.rmtree(backup, ignore_errors=True)
            shutil.move(str(dest), str(backup))
            try:
                shutil.copytree(skill_src, dest)
                manifest[skill_name] = bundled_hash
                updated.append(skill_name)
                if not quiet:
                    print(f"  ↑ {skill_name} (updated)")
                shutil.rmtree(backup, ignore_errors=True)
            except (OSError, IOError):
                if backup.exists() and not dest.exists():
                    shutil.move(str(backup), str(dest))
                raise
        except (OSError, IOError) as e:
            if not quiet:
                print(f"  ! Failed to update {skill_name}: {e}")

    cleaned = sorted(set(manifest.keys()) - bundled_names)
    for name in cleaned:
        del manifest[name]

    for desc_md in bundled_dir.rglob("DESCRIPTION.md"):
        rel = desc_md.relative_to(bundled_dir)
        dest_desc = SKILLS_DIR / rel
        if dest_desc.exists():
            continue
        try:
            dest_desc.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(desc_md, dest_desc)
        except (OSError, IOError) as e:
            logger.debug("Could not copy %s: %s", desc_md, e)

    _write_manifest(manifest)

    return {
        "copied": copied,
        "updated": updated,
        "skipped": skipped,
        "user_modified": user_modified,
        "cleaned": cleaned,
        "total_bundled": len(bundled_skills),
    }


if __name__ == "__main__":
    print("Syncing bundled skills into ~/.hermes/skills/ ...")
    result = sync_skills(quiet=False)
    parts = [
        f"{len(result['copied'])} new",
        f"{len(result['updated'])} updated",
        f"{result['skipped']} unchanged",
    ]
    if result["user_modified"]:
        parts.append(f"{len(result['user_modified'])} user-modified (kept)")
    if result["cleaned"]:
        parts.append(f"{len(result['cleaned'])} cleaned from manifest")
    print(f"\nDone: {', '.join(parts)}, {result['total_bundled']} total bundled.")
