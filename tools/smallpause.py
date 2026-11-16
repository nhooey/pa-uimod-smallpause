#!/usr/bin/env python3
"""smallpause: the commands for working on the Small Pause mod.

The functions above `main`'s shell are pure: they take parsed values and
return values, so tests/test_smallpause.py checks them without the game or
the file system. `main` and the `run_*` functions do the reading, copying and
printing.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Sequence

MANIFEST = "modinfo.json"

# The fields the game and PA Mod Manager (PAMM) need to load and list the mod.
REQUIRED_FIELDS = ("context", "identifier", "display_name", "version", "id", "scenes")

# What the game loads from the mod's directory: the manifest and the scripts
# its scenes name. `img/` holds README screenshots and the icon PAMM fetches
# from GitHub, so a local install leaves it out.
INSTALLED_PATHS = (MANIFEST, "ui")

VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
RAW_GITHUB_PATTERN = re.compile(
    r"^https://raw\.githubusercontent\.com/[^/]+/[^/]+/[^/]+/(.+)$"
)
CLIENT_MODS_ENV = "PA_CLIENT_MODS"

# Where Planetary Annihilation reads client mods on each platform, relative
# to the base directory named by the first element.
CLIENT_MODS_BY_PLATFORM: Mapping[str, tuple[str, str]] = {
    "darwin": (
        "HOME",
        "Library/Application Support/Uber Entertainment/Planetary Annihilation/client_mods",
    ),
    "linux": ("HOME", ".local/Uber Entertainment/Planetary Annihilation/client_mods"),
    "win32": ("LOCALAPPDATA", "Uber Entertainment/Planetary Annihilation/client_mods"),
}


# ---------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------


def is_filled(value: object) -> bool:
    return value is not None and value != ""


def scene_scripts(manifest: Mapping[str, object]) -> tuple[str, ...]:
    """Every script URL listed under the manifest's scenes, in order."""
    scenes = manifest.get("scenes")
    return (
        tuple(url for urls in scenes.values() if isinstance(urls, list) for url in urls)
        if isinstance(scenes, dict)
        else ()
    )


def coui_path(url: object) -> str | None:
    """The repository path a coui:// URL names, or None for any other URL."""
    return (
        url[len("coui://") :]
        if isinstance(url, str) and url.startswith("coui://")
        else None
    )


def icon_path(url: str) -> str | None:
    """The repository path of a raw.githubusercontent.com icon URL, after the branch."""
    match = RAW_GITHUB_PATTERN.match(url)
    return match.group(1) if match else None


def is_safe_relative(path: str) -> bool:
    """True when `path` stays inside the directory it is joined to."""
    parts = PurePosixPath(path).parts
    return bool(parts) and not PurePosixPath(path).is_absolute() and ".." not in parts


def field_problems(manifest: Mapping[str, object]) -> tuple[str, ...]:
    missing = tuple(
        f'{MANIFEST} has no "{field}"'
        for field in REQUIRED_FIELDS
        if not is_filled(manifest.get(field))
    )
    version = manifest.get("version")
    return (
        missing
        + (
            ()
            if manifest.get("context") == "client"
            else (f'{MANIFEST} context is not "client"',)
        )
        + (
            ()
            if isinstance(version, str) and VERSION_PATTERN.match(version)
            else (f"{MANIFEST} version is not MAJOR.MINOR.PATCH",)
        )
    )


def scene_problems(
    manifest: Mapping[str, object], exists: Callable[[str], bool]
) -> tuple[str, ...]:
    scripts = scene_scripts(manifest)

    def problem(url: object) -> str | None:
        path = coui_path(url)
        return (
            f"scene script {url} is not a coui:// URL"
            if path is None
            else f"scene script {url} leaves the repository"
            if not is_safe_relative(path)
            else None
            if exists(path)
            else f"scene script {url} has no file at {path}"
        )

    return (() if scripts else (f"{MANIFEST} scenes lists no scripts",)) + tuple(
        p for p in map(problem, scripts) if p is not None
    )


def icon_problems(
    manifest: Mapping[str, object], exists: Callable[[str], bool]
) -> tuple[str, ...]:
    """PAMM shows the icon from GitHub's raw host, so the path after the branch must exist here."""
    icon = manifest.get("icon")
    if not is_filled(icon):
        return ()
    path = icon_path(icon) if isinstance(icon, str) else None
    return (
        (f"icon {icon} is not a raw.githubusercontent.com URL",)
        if path is None
        else ()
        if is_safe_relative(path) and exists(path)
        else (f"icon {icon} has no file at {path}",)
    )


def manifest_problems(
    manifest: object, exists: Callable[[str], bool]
) -> tuple[str, ...]:
    """Every reason the game or PAMM couldn't load this manifest; empty when it's sound.

    `exists` answers whether a repository-relative path is a file.
    """
    if not isinstance(manifest, dict):
        return (f"{MANIFEST} is not a JSON object",)
    return (
        field_problems(manifest)
        + scene_problems(manifest, exists)
        + icon_problems(manifest, exists)
    )


def default_client_mods(platform: str, environ: Mapping[str, str]) -> Path | None:
    """The game's client_mods directory: $PA_CLIENT_MODS, else the platform's usual place."""
    if environ.get(CLIENT_MODS_ENV):
        return Path(environ[CLIENT_MODS_ENV])
    base_var, relative = CLIENT_MODS_BY_PLATFORM.get(
        "linux" if platform.startswith("linux") else platform, (None, None)
    )
    return (
        Path(environ[base_var], relative)
        if base_var and environ.get(base_var)
        else None
    )


def find_root(start: Path, has_manifest: Callable[[Path], bool]) -> Path | None:
    """The nearest directory at or above `start` holding modinfo.json."""
    return next((d for d in (start, *start.parents) if has_manifest(d)), None)


@dataclass(frozen=True, slots=True)
class Plan:
    """What `install` or `uninstall` will do, or why it won't."""

    destination: Path
    replaces: bool
    refusal: str | None


def install_plan(
    destination: Path, existing_identifier: str | None, identifier: str, exists: bool
) -> Plan:
    """Replace a copy only when it is this mod's: never overwrite another mod's directory."""
    return Plan(
        destination=destination,
        replaces=exists,
        refusal=(
            None
            if not exists or existing_identifier == identifier
            else f"{destination} exists and is not a copy of {identifier}; move it aside first"
        ),
    )


def uninstall_plan(
    destination: Path, existing_identifier: str | None, identifier: str, exists: bool
) -> Plan:
    return Plan(
        destination=destination,
        replaces=exists,
        refusal=(
            f"{destination} does not exist; nothing to remove"
            if not exists
            else None
            if existing_identifier == identifier
            else f"{destination} is not a copy of {identifier}; leaving it alone"
        ),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smallpause",
        description="Commands for working on the Small Pause Planetary Annihilation mod.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        help="the mod's checkout (default: the nearest directory at or above the current one holding modinfo.json)",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    commands.add_parser(
        "check-modinfo",
        help="check modinfo.json parses, has the fields the game reads, and names files that exist",
        description="Check that modinfo.json is a manifest the game can load: valid JSON with the fields "
        "the game and PAMM read, and every coui:// scene script and the icon resolving to a file.",
    )

    def add_client_mods(sub: argparse.ArgumentParser) -> argparse.ArgumentParser:
        sub.add_argument(
            "--client-mods",
            type=Path,
            help=f"the game's client_mods directory (default: ${CLIENT_MODS_ENV}, else the platform's usual place)",
        )
        sub.add_argument(
            "-n",
            "--dry-run",
            action="store_true",
            help="say what would change, change nothing",
        )
        return sub

    add_client_mods(
        commands.add_parser(
            "install",
            help="copy the mod into the game's client_mods directory to try a change",
            description="Copy modinfo.json and ui/ into <client_mods>/<identifier>, replacing an earlier "
            'copy of this mod. Then enable "Small Pause Dialogue" under PAMM\'s UI Mods and pause a game.',
        )
    )
    add_client_mods(
        commands.add_parser(
            "uninstall",
            help="remove the copy `install` made from the game's client_mods directory",
            description="Remove <client_mods>/<identifier> when it holds this mod's modinfo.json.",
        )
    )
    return parser


# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------


def read_manifest(path: Path) -> tuple[object, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"{path} does not exist"
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return None, f"{path} is not valid JSON: {error}"


def identifier_at(directory: Path) -> str | None:
    manifest, _ = read_manifest(directory / MANIFEST)
    return manifest.get("identifier") if isinstance(manifest, dict) else None


def run_check(root: Path) -> int:
    manifest, error = read_manifest(root / MANIFEST)
    problems = (
        (error,)
        if error
        else manifest_problems(manifest, lambda p: (root / p).is_file())
    )
    for problem in problems:
        print(f"FAIL: {problem}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} {MANIFEST} check(s) failed", file=sys.stderr)
        return 1
    print(f"{MANIFEST} OK")
    return 0


def resolve_client_mods(arg: Path | None) -> Path | None:
    found = arg or default_client_mods(sys.platform, os.environ)
    if found is None:
        print(
            f"error: no client_mods directory known here; pass --client-mods or set ${CLIENT_MODS_ENV}",
            file=sys.stderr,
        )
    return found


def run_install(root: Path, client_mods: Path | None, dry_run: bool) -> int:
    identifier = identifier_at(root)
    if client_mods is None or identifier is None:
        if identifier is None:
            print(
                f"error: {root / MANIFEST} has no identifier; run `smallpause check-modinfo`",
                file=sys.stderr,
            )
        return 1
    destination = client_mods / identifier
    plan = install_plan(
        destination, identifier_at(destination), identifier, destination.exists()
    )
    if plan.refusal:
        print(f"error: {plan.refusal}", file=sys.stderr)
        return 1
    verb = "replace" if plan.replaces else "create"
    print(
        f"{'would ' + verb if dry_run else verb.capitalize() + 'd'} {destination} from {root}"
    )
    if dry_run:
        return 0
    if plan.replaces:
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for name in INSTALLED_PATHS:
        source = root / name
        (shutil.copytree if source.is_dir() else shutil.copy2)(
            source, destination / name
        )
    return 0


def run_uninstall(root: Path, client_mods: Path | None, dry_run: bool) -> int:
    identifier = identifier_at(root)
    if client_mods is None or identifier is None:
        if identifier is None:
            print(
                f"error: {root / MANIFEST} has no identifier; run `smallpause check-modinfo`",
                file=sys.stderr,
            )
        return 1
    destination = client_mods / identifier
    plan = uninstall_plan(
        destination, identifier_at(destination), identifier, destination.exists()
    )
    if plan.refusal:
        print(f"error: {plan.refusal}", file=sys.stderr)
        return 1
    print(f"{'would remove' if dry_run else 'Removed'} {destination}")
    if not dry_run:
        shutil.rmtree(destination)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root or find_root(Path.cwd(), lambda d: (d / MANIFEST).is_file())
    if root is None:
        print(
            f"error: no {MANIFEST} at or above {Path.cwd()}; pass --root",
            file=sys.stderr,
        )
        return 2
    match args.command:
        case "check-modinfo":
            return run_check(root)
        case "install":
            client_mods = resolve_client_mods(args.client_mods)
            return run_install(root, client_mods, args.dry_run)
        case "uninstall":
            client_mods = resolve_client_mods(args.client_mods)
            return run_uninstall(root, client_mods, args.dry_run)
    return 2


if __name__ == "__main__":
    sys.exit(main())
