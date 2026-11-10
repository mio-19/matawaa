rec {
  patches =
    let
      dir = ./patches;
      categories = [
        "00-mobile-nixos-upstream-candidates"
        "10-asteroidos-upstream-nightly"
        "20-our-customizations-apps"
        "25-asteroidos-upstream-nightly-apps"
        "30-our-customizations-devices"
        "40-our-experimental-customizations"
        "50-upstream-unmerged-development"
      ];
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
