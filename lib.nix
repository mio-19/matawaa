rec {
  patches =
    let
      dir = ./patches;
      entries = builtins.readDir dir;
      isPatch = name: entries.${name} == "regular" && builtins.match ".*\\.patch$" name != null;
      patchNames = builtins.sort (a: b: a < b) (builtins.filter isPatch (builtins.attrNames entries));
    in
    map (name: dir + "/${name}") patchNames;

  mkPatchedMobileNixos =
    { pkgs, mobile-nixos }:
    pkgs.applyPatches {
      name = "mobile-nixos-smartwatch";
      src = mobile-nixos;
      inherit patches;
    };
}
