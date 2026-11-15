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

## Building and testing

There is no build step and no automated test. To try a change, copy the
checkout into the game's `client_mods/` directory (on macOS,
`~/Library/Application Support/Uber Entertainment/Planetary Annihilation/client_mods/`),
enable "Small Pause Dialogue" under PAMM's UI Mods, and pause a game.

`nix develop` enters the dev shell, which installs the agent skills in
`skills-devshell/`; `nix flake check` checks the flake.

## Style

Indent with spaces, never tabs.
