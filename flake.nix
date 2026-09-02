{
  description = "fuddy-duddy development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      python = pkgs.python312;

      # Pyxel is not packaged in nixpkgs, so the shellHook installs it from
      # PyPI into .venv. Its wheel bundles SDL2 statically, but SDL2 dlopens
      # the platform libraries below at runtime.
      runtimeLibs = with pkgs; [
        libGL
        mesa
        libxkbcommon
        wayland
        alsa-lib
        libpulseaudio
        libx11
        libxext
        libxcursor
        libxi
        libxfixes
        libxrandr
        libxrender
        libxinerama
        libxscrnsaver
      ];
    in {
      devShells.${system}.default = pkgs.mkShell {
        packages = [
          python
          pkgs.strace
        ];

        # GL comes from nix's own mesa (works on non-NixOS hosts too);
        # /run/opengl-driver/lib lets NixOS hosts provide their driver instead.
        env.LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath runtimeLibs
          + ":/run/opengl-driver/lib";
        env.LIBGL_DRIVERS_PATH = "${pkgs.mesa}/lib/dri";

        shellHook = ''
          if [ ! -d .venv ]; then
            ${python}/bin/python -m venv .venv
            .venv/bin/pip -q install --upgrade pip
            .venv/bin/pip -q install pyxel pytest
          fi
          source .venv/bin/activate
          export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
        '';
      };
    };
}
