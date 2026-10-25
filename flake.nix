{
  description = "Matawaa - Smartwatch support patchset on top of Mobile NixOS";

  inputs = {
    nixpkgs.url = "https://nixos.org/channels/nixos-unstable/nixexprs.tar.zst";
    mobile-nixos = {
      url = "github:NixOS/mobile-nixos/development";
      flake = false;
    };
    nix-systems.url = "github:nix-systems/default-linux";
  };

  outputs =
    {
      self,
      nixpkgs,
      mobile-nixos,
      nix-systems,
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
    };
}
