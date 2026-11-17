{
  description = "pa-uimod-smallpause dev-shell skill set: an isolated sub-flake the root dev shell runs at startup, never a root input, so the skill sources live only in this flake's lock.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    systems.url = "github:nix-systems/default";

    # The builder library; it carries no skill inputs.
    agent-skill-flake = {
      url = "github:nhooey/agent-skill-flake";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # skillspkgs' per-family skill combinations. It follows `nixpkgs` but not
    # `agent-skill-flake`, so it keeps its own compatible builder.
    skillspkgs-combinations = {
      url = "github:nhooey/skillspkgs?dir=sources/combinations";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      agent-skill-flake,
      ...
    }@inputs:
    agent-skill-flake.lib.mkDevshellSkillsFlake {
      inherit nixpkgs;
      systems = import inputs.systems;
      name = "pa-uimod-smallpause-devshell";
      sources = [
        # The browser-extensions-and-game-mods family's combination, the
        # one skill source. The mod needs nothing the rest of its family
        # doesn't, so there are no additions.
        { source = inputs.skillspkgs-combinations.combinations.browser-extensions-and-game-mods; }
      ];
    };
}
