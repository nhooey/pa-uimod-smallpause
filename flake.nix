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
  };

  outputs =
    { flake-parts, systems, ... }@inputs:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = import systems;
      imports = [ inputs.agent-skill-flake.flakeModules.devshellSkills ];

      agent-skill-flake.devshellSkills.name = "pa-uimod-smallpause";
    };
}
