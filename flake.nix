{
  description = "pa-uimod-smallpause: a Planetary Annihilation UI mod that shrinks the pause dialogue";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };
    systems.url = "github:nix-systems/default";
    # The builder library, not a skill: its `devshellSkills` module runs the
    # `skills-devshell/` sub-flake when the dev shell starts, so this flake
    # carries no skill inputs.
    agent-skill-flake = {
      url = "github:nhooey/agent-skill-flake";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    { flake-parts, systems, ... }@inputs:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = import systems;
      imports = [
        inputs.agent-skill-flake.flakeModules.devshellSkills
        inputs.treefmt-nix.flakeModule
      ];

      agent-skill-flake.devshellSkills.name = "pa-uimod-smallpause";

      perSystem =
        { pkgs, ... }:
        let
          # tools/smallpause.py is standard-library Python; the package only
          # puts it on PATH under the nixpkgs interpreter.
          smallpause = pkgs.writeShellApplication {
            name = "smallpause";
            runtimeInputs = [ pkgs.python3 ];
            text = ''exec python3 ${./tools/smallpause.py} "$@"'';
          };
        in
        {
          packages.default = smallpause;
          packages.smallpause = smallpause;

          devshells.default = {
            packages = [ pkgs.python3 ];
            commands = [
              {
                category = "dev";
                package = smallpause;
                help = "Check modinfo.json, or install the mod into the game's client_mods to try it (smallpause --help)";
              }
              {
                category = "ci";
                name = "unit-test";
                help = "Run smallpause's unit tests";
                command = ''python3 -m unittest discover -s "$(git rev-parse --show-toplevel 2>/dev/null || echo "$PRJ_ROOT")/tests" "$@"'';
              }
            ];
          };

          # The game loads the mod from modinfo.json alone, so a broken
          # manifest or scene path fails silently in-game; `smallpause
          # check-modinfo` catches both without the game.
          checks.modinfo = pkgs.runCommand "modinfo-check" { } ''
            ${pkgs.lib.getExe smallpause} --root ${./.} check-modinfo
            touch $out
          '';

          checks.unit-tests =
            pkgs.runCommand "smallpause-unit-tests" { nativeBuildInputs = [ pkgs.python3 ]; }
              ''
                cp -r ${./.} src && chmod -R u+w src && cd src
                python3 -m unittest discover -s tests -v
                touch $out
              '';

          # treefmt-nix also adds `checks.<system>.treefmt`, so `nix flake
          # check` fails on any unformatted file.
          treefmt = {
            projectRootFile = "flake.nix";
            programs.nixfmt.enable = true;
            programs.ruff-format.enable = true;
            settings.global.excludes = [
              ".agents/**" # installed third-party skills, not ours to reformat
              ".claude/**"
            ];
          };
        };
    };
}
