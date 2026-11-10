rec {
  patches =
    let
      dir = ./patches;
      entries = builtins.readDir dir;
      categories = builtins.sort (a: b: a < b) (
        builtins.filter
          (name: entries.${name} == "directory")
          (builtins.attrNames entries)
      );
      categoryPatches = category:
        let
          categoryDir = dir + "/${category}";
          entries = builtins.readDir categoryDir;
          isPatch = name: entries.${name} == "regular" && builtins.match ".*\\.patch$" name != null;
          names = builtins.sort (a: b: a < b) (builtins.filter isPatch (builtins.attrNames entries));
        in
        map (name: categoryDir + "/${name}") names;
    in
    builtins.concatMap categoryPatches categories;

  mkPatchedMobileNixos =
    { pkgs, mobile-nixos }:
    pkgs.applyPatches {
      name = "mobile-nixos-smartwatch";
      src = mobile-nixos;
      inherit patches;
    };
}
