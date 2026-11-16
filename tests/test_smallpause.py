"""Tests for tools/smallpause.py's argument parsing and pure core.

Run with `python3 -m unittest discover -s tests` from the repository root;
`nix flake check` runs them too.
"""

import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import smallpause as sp  # noqa: E402

GOOD = {
    "context": "client",
    "identifier": "com.example.mod",
    "display_name": "Example",
    "version": "1.2.3",
    "id": "example",
    "scenes": {"live_game_paused_popup": ["coui://ui/mods/example/example.js"]},
    "icon": "https://raw.githubusercontent.com/someone/repo/master/img/icon.png",
}
FILES = frozenset({"ui/mods/example/example.js", "img/icon.png"})


def exists(path):
    return path in FILES


class ManifestProblems(unittest.TestCase):
    def test_sound_manifest_has_none(self):
        self.assertEqual(sp.manifest_problems(GOOD, exists), ())

    def test_not_an_object(self):
        self.assertEqual(
            sp.manifest_problems([], exists), ("modinfo.json is not a JSON object",)
        )

    def test_missing_and_empty_fields(self):
        manifest = {k: v for k, v in GOOD.items() if k != "id"} | {"display_name": ""}
        problems = sp.manifest_problems(manifest, exists)
        self.assertIn('modinfo.json has no "id"', problems)
        self.assertIn('modinfo.json has no "display_name"', problems)

    def test_context_must_be_client(self):
        self.assertEqual(
            sp.manifest_problems(GOOD | {"context": "server"}, exists),
            ('modinfo.json context is not "client"',),
        )

    def test_version_must_be_semver(self):
        for version in ("1.0", "v1.0.0", 1, None):
            with self.subTest(version=version):
                self.assertIn(
                    "modinfo.json version is not MAJOR.MINOR.PATCH",
                    sp.manifest_problems(GOOD | {"version": version}, exists),
                )

    def test_scene_script_checks(self):
        cases = {
            "http://x/a.js": "scene script http://x/a.js is not a coui:// URL",
            "coui://ui/missing.js": "scene script coui://ui/missing.js has no file at ui/missing.js",
            "coui://../outside.js": "scene script coui://../outside.js leaves the repository",
            "coui:///etc/passwd": "scene script coui:///etc/passwd leaves the repository",
        }
        for url, problem in cases.items():
            with self.subTest(url=url):
                manifest = GOOD | {"scenes": {"s": [url]}}
                self.assertEqual(sp.manifest_problems(manifest, exists), (problem,))

    def test_scenes_must_list_a_script(self):
        self.assertIn(
            "modinfo.json scenes lists no scripts",
            sp.manifest_problems(GOOD | {"scenes": {"s": []}}, exists),
        )

    def test_scene_must_be_a_list(self):
        # The game reads each scene as a list of URLs; a bare string is
        # not loaded, even beside a sound scene.
        scenes = GOOD["scenes"] | {"other": "coui://ui/mods/example/example.js"}
        self.assertEqual(
            sp.manifest_problems(GOOD | {"scenes": scenes}, exists),
            ("modinfo.json scene other is not a list of scripts",),
        )

    def test_icon_checks(self):
        self.assertEqual(
            sp.manifest_problems(
                {k: v for k, v in GOOD.items() if k != "icon"}, exists
            ),
            (),
        )
        self.assertEqual(
            sp.manifest_problems(
                GOOD | {"icon": "https://example.com/icon.png"}, exists
            ),
            (
                "icon https://example.com/icon.png is not a raw.githubusercontent.com URL",
            ),
        )
        missing = "https://raw.githubusercontent.com/a/b/master/img/gone.png"
        self.assertEqual(
            sp.manifest_problems(GOOD | {"icon": missing}, exists),
            (f"icon {missing} has no file at img/gone.png",),
        )

    def test_repository_manifest_is_sound(self):
        root = Path(__file__).resolve().parent.parent
        manifest, error = sp.read_manifest(root / "modinfo.json")
        self.assertIsNone(error)
        self.assertEqual(
            sp.manifest_problems(manifest, lambda p: (root / p).is_file()), ()
        )


class ClientMods(unittest.TestCase):
    def test_environment_variable_wins(self):
        self.assertEqual(
            sp.default_client_mods("darwin", {"PA_CLIENT_MODS": "/x", "HOME": "/h"}),
            Path("/x"),
        )

    def test_platform_defaults(self):
        self.assertEqual(
            sp.default_client_mods("darwin", {"HOME": "/h"}),
            Path(
                "/h/Library/Application Support/Uber Entertainment/Planetary Annihilation/client_mods"
            ),
        )
        self.assertEqual(
            sp.default_client_mods("linux", {"HOME": "/h"}),
            Path("/h/.local/Uber Entertainment/Planetary Annihilation/client_mods"),
        )

    def test_unknown_platform_or_missing_base(self):
        self.assertIsNone(sp.default_client_mods("sunos5", {"HOME": "/h"}))
        self.assertIsNone(sp.default_client_mods("darwin", {}))


class Plans(unittest.TestCase):
    dest = Path("/mods/com.example.mod")

    def test_install_fresh_and_replace(self):
        self.assertEqual(
            sp.install_plan(self.dest, None, "com.example.mod", False),
            sp.Plan(self.dest, False, None),
        )
        self.assertEqual(
            sp.install_plan(self.dest, "com.example.mod", "com.example.mod", True),
            sp.Plan(self.dest, True, None),
        )

    def test_install_refuses_another_directory(self):
        self.assertIsNotNone(
            sp.install_plan(self.dest, None, "com.example.mod", True).refusal
        )
        self.assertIsNotNone(
            sp.install_plan(self.dest, "other", "com.example.mod", True).refusal
        )

    def test_uninstall(self):
        self.assertIsNone(
            sp.uninstall_plan(
                self.dest, "com.example.mod", "com.example.mod", True
            ).refusal
        )
        self.assertIsNotNone(
            sp.uninstall_plan(self.dest, None, "com.example.mod", False).refusal
        )
        self.assertIsNotNone(
            sp.uninstall_plan(self.dest, "other", "com.example.mod", True).refusal
        )


class FindRoot(unittest.TestCase):
    def test_nearest_ancestor(self):
        self.assertEqual(
            sp.find_root(Path("/a/b/c"), lambda d: d == Path("/a")), Path("/a")
        )
        self.assertIsNone(sp.find_root(Path("/a/b"), lambda d: False))


class Parser(unittest.TestCase):
    def parse(self, *argv):
        return sp.build_parser().parse_args(argv)

    def test_commands_and_options(self):
        args = self.parse("--root", "/r", "install", "--client-mods", "/m", "-n")
        self.assertEqual(
            (args.root, args.command, args.client_mods, args.dry_run),
            (Path("/r"), "install", Path("/m"), True),
        )
        self.assertEqual(self.parse("check-modinfo").command, "check-modinfo")
        self.assertFalse(self.parse("uninstall").dry_run)

    def test_command_is_required_and_known(self):
        for argv in ((), ("frobnicate",)):
            with (
                self.subTest(argv=argv),
                self.assertRaises(SystemExit),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                self.parse(*argv)

    def test_help_lists_every_command(self):
        text = sp.build_parser().format_help()
        for command in ("check-modinfo", "install", "uninstall", "--root"):
            self.assertIn(command, text)


if __name__ == "__main__":
    unittest.main()
