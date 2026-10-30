let
  flakeLock = builtins.fromJSON (builtins.readFile ./flake.lock);
  mobileNixosLock = flakeLock.nodes.mobile-nixos.locked;
  nixpkgsLock = flakeLock.nodes.nixpkgs.locked;

  # Use the exact nixpkgs revision the flake pins, so plain `nix-build`
  # matches `nix build`. The flake tracks the 26.05 branch for Qt 6.11.2,
  # the version AsteroidOS upstream builds against.
  nixpkgsSrc =
    if nixpkgsLock ? url then
      builtins.fetchTarball {
        url = nixpkgsLock.url;
        sha256 = nixpkgsLock.narHash;
      }
    else
      builtins.fetchTarball {
        url = "https://github.com/${nixpkgsLock.owner}/${nixpkgsLock.repo}/archive/${nixpkgsLock.rev}.tar.gz";
        sha256 = nixpkgsLock.narHash;
      };
in
{
  pkgs ? import nixpkgsSrc { },
  mobile-nixos ? builtins.fetchTarball {
    url = "https://github.com/${mobileNixosLock.owner}/${mobileNixosLock.repo}/archive/${mobileNixosLock.rev}.tar.gz";
    sha256 = mobileNixosLock.narHash;
  },
  ...
}@args:

let
  lib = import ./lib.nix;
  patchedMobileNixos = lib.mkPatchedMobileNixos { inherit pkgs mobile-nixos; };
in
import "${patchedMobileNixos}" (
  builtins.removeAttrs args [
    "pkgs"
    "mobile-nixos"
  ]
)
