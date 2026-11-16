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
        {
          # The game loads the mod from modinfo.json alone, so a broken
          # manifest or scene path fails silently in-game;
          # tests/check-modinfo.sh catches both without the game.
          checks.modinfo =
            pkgs.runCommand "modinfo-check"
              {
                nativeBuildInputs = [
                  pkgs.bash
                  pkgs.jq
                ];
              }
              ''
                bash ${./tests/check-modinfo.sh} ${./.}
                touch $out
              '';

          # treefmt-nix also adds `checks.<system>.treefmt`, so `nix flake
          # check` fails on any unformatted file.
          treefmt = {
            projectRootFile = "flake.nix";
            programs.nixfmt.enable = true;
            settings.global.excludes = [
              ".agents/**" # installed third-party skills, not ours to reformat
              ".claude/**"
            ];
          };
        };
    };
}
