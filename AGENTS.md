# Small Pause

A client UI mod for the real-time strategy game Planetary Annihilation. It
shrinks the pause dialogue and its button so they stay out of the way of the
rest of the interface while the game is paused.

## Layout

- `modinfo.json`: the mod's manifest, read by the game and by PA Mod Manager
  (PAMM). Its `scenes` key loads the script into the `live_game_paused_popup`
  scene; `version`, `date` and `build` change with each release.
- `ui/mods/smallpause/smallpause.js`: the mod itself, jQuery calls that
  restyle the pause popup's elements.
- `img/`: the icon and the screenshots the README shows.
- `tools/smallpause.py`: the `smallpause` command, standard-library Python.

## Building and testing

There is no build step. `nix develop` enters the dev shell, which installs
the agent skills in `skills-devshell/`; `menu` lists its commands:

- `check`: `nix flake check`, which runs `smallpause check-modinfo`, the
  unit tests and the formatting check.
- `smallpause check-modinfo`: checks that `modinfo.json` parses, has the
  fields the game reads, and that each `coui://` scene script and the icon
  exist in the repository.
- `unit-test`: runs `tests/test_smallpause.py`, the tests of
  `tools/smallpause.py`.
- `fmt`: formats Nix and Python with treefmt.
- `smallpause install`: copies the mod into the game's `client_mods/`
  directory (`--client-mods` or `$PA_CLIENT_MODS` names another, `-n` only
  says what it would do); `smallpause uninstall` removes that copy.

Nothing checks the restyle itself: to try a change, run `smallpause install`,
enable "Small Pause Dialogue" under PAMM's UI Mods, and pause a game.

## Style

Indent with spaces, never tabs.
