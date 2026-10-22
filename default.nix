let
  mobileNixosLock = (builtins.fromJSON (builtins.readFile ./flake.lock)).nodes.mobile-nixos.locked;
in
{
  pkgs ? import <nixpkgs> { },
  mobile-nixos ? builtins.fetchGit {
    url = "https://github.com/${mobileNixosLock.owner}/${mobileNixosLock.repo}.git";
    rev = mobileNixosLock.rev;
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
