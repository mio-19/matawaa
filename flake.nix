{
  description = "Matawaa - Smartwatch support patchset on top of Mobile NixOS";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    mobile-nixos = {
      url = "github:NixOS/mobile-nixos/development";
      flake = false;
    };
    nix-systems.url = "github:nix-systems/default-linux";
    deploy-rs = {
      url = "github:serokell/deploy-rs";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      mobile-nixos,
      nix-systems,
      deploy-rs,
    }:
    let
      systems = import nix-systems;
      forAllSystems = nixpkgs.lib.genAttrs systems;

      matawaaLib = import ./lib.nix;
      inherit (matawaaLib) patches;

      mkPatchedMobileNixos = pkgs: matawaaLib.mkPatchedMobileNixos { inherit pkgs mobile-nixos; };

      allDevices = [
        # Smartwatch devices
        "asus-anthias"
        "asus-sparrow"
        "asus-swift"
        "asus-wren"
        "casio-koi"
        "fossil-firefish"
        "fossil-hoki"
        "fossil-hoki-mainline"
        "fossil-ray"
        "fossil-triggerfish"
        "google-aurora"
        "lg-bass"
        "lg-dory"
        "lg-lenok"
        "lg-narwhal"
        "lg-nemo"
        "motorola-minnow"
        "motorola-smelt"
        "oppo-beluga"
        "oppo-beluga-mainline"
        "polar-pike"
        "samsung-rinato"
        "samsung-sprat"
        "sony-tetra"
        "ticwatch-catfish"
        "ticwatch-harmony"
        "ticwatch-inharmony"
        "ticwatch-mooneye"
        "ticwatch-rubyfish"
        "ticwatch-skipjack"
        "ticwatch-tunny"
        # Existing Mobile-NixOS devices
        "acer-juniper"
        "acer-lazor"
        "asus-dumo"
        "lenovo-krane"
        "lenovo-wormdingler"
        "motorola-potter"
        "oneplus-enchilada"
        "oneplus-fajita"
        "pine64-pinephone"
        "pine64-pinephonepro"
        "pine64-pinetab"
        "uefi-x86_64"
      ];
    in
    {
      inherit patches;

      lib = {
        inherit mkPatchedMobileNixos allDevices;

        # Helper to construct a device-specific NixOS module
        mkDeviceModule =
          device:
          {
            config,
            lib,
            pkgs,
            ...
          }:
          {
            imports = [
              (import "${self.lib.mkPatchedMobileNixos pkgs}/lib/configuration.nix" { inherit device; })
            ];
          };

        # Helper to construct a full AsteroidOS smartwatch NixOS system configuration
        mkWatchConfiguration =
          {
            device,
            system ? "x86_64-linux",
          }:
          let
            pkgs = nixpkgs.legacyPackages.${system};
            patchedMobileNixos = mkPatchedMobileNixos pkgs;
            eval = import "${patchedMobileNixos}/examples/asteroid" {
              inherit device;
              pkgs = import "${patchedMobileNixos}/pkgs.nix" { inherit system; };
              additionalConfiguration = {
                nixpkgs.buildPlatform = system;
              };
            };
          in
          eval.eval;
      };

      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          patchedMobileNixos = mkPatchedMobileNixos pkgs;
        in
        {
          patched-mobile-nixos = patchedMobileNixos;
          default = patchedMobileNixos;
        }
      );

      nixosModules =
        builtins.listToAttrs (
          map (device: {
            name = device;
            value = self.lib.mkDeviceModule device;
          }) allDevices
        )
        // {
          default =
            {
              config,
              lib,
              pkgs,
              ...
            }:
            {
              imports = [
                (import "${self.lib.mkPatchedMobileNixos pkgs}/lib/configuration.nix" { })
              ];
            };
        };

      overlays = {
        default =
          final: super: (import "${self.lib.mkPatchedMobileNixos super}/overlay/default.nix" final super);
        cross =
          final: super:
          (import "${self.lib.mkPatchedMobileNixos super}/overlay/cross-compile.nix" final super);
      };

      nixosConfigurations = {
        "fossil-hoki" = self.lib.mkWatchConfiguration { device = "fossil-hoki"; };
        "fossil-hoki-mainline" = self.lib.mkWatchConfiguration { device = "fossil-hoki-mainline"; };
        "oppo-beluga" = self.lib.mkWatchConfiguration { device = "oppo-beluga"; };
        "oppo-beluga-mainline" = self.lib.mkWatchConfiguration { device = "oppo-beluga-mainline"; };
      };

      deploy = {
        magicRollback = false;
        autoRollback = false;
        nodes = {
          "fossil-hoki" = {
            hostname = "172.16.42.1";
            profiles.system = {
              user = "root";
              sshUser = "ceres";
              path =
                deploy-rs.lib.x86_64-linux.activate.custom
                  self.nixosConfigurations."fossil-hoki".config.system.build.toplevel
                  ''
                    $PROFILE/bin/switch-to-configuration boot
                  '';
            };
          };
          "fossil-hoki-mainline" = {
            hostname = "172.16.42.1";
            profiles.system = {
              user = "root";
              sshUser = "ceres";
              path =
                deploy-rs.lib.x86_64-linux.activate.custom
                  self.nixosConfigurations."fossil-hoki-mainline".config.system.build.toplevel
                  ''
                    $PROFILE/bin/switch-to-configuration boot
                  '';
            };
          };
          "oppo-beluga" = {
            hostname = "172.16.42.1";
            profiles.system = {
              user = "root";
              sshUser = "ceres";
              path =
                deploy-rs.lib.x86_64-linux.activate.custom
                  self.nixosConfigurations."oppo-beluga".config.system.build.toplevel
                  ''
                    $PROFILE/bin/switch-to-configuration boot
                  '';
            };
          };
          "oppo-beluga-mainline" = {
            hostname = "172.16.42.1";
            profiles.system = {
              user = "root";
              sshUser = "ceres";
              path =
                deploy-rs.lib.x86_64-linux.activate.custom
                  self.nixosConfigurations."oppo-beluga-mainline".config.system.build.toplevel
                  ''
                    $PROFILE/bin/switch-to-configuration boot
                  '';
            };
          };
        };
      };
    };
}
