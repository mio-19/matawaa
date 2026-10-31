# Matawaa

this project aims to bring a better open source operating system experience to commercially available smartwatches. this project forks [Mobile-NixOS](https://mobile.nixos.org/) and adapt it for smartwatches by building on the existing works of [AsteroidOS](https://asteroidos.org/). this project will be able to package asteroid os with the nix package manager and improve the usability on top of asteroid os. this project will be able to implement an atomic upgrade procedure similar to NixOS; while the AsteroidOS currently does not have a good way to upgrade without losing data. this project will implement encryption based on the existing works done by mobile-nixos. Then this project will implement common smartwatches features on top of AsteroidOS, like "find my phone". this project will also develop AsteroidOS apps. For changes that make sense to upstream to AsteroidOS, this project will seek to upstream them.

Patched versions of android companion apps will be in [this repo](https://github.com/mio-19/repo)

## Development

This project is a patchset on top of [Mobile-NixOS](https://mobile.nixos.org/). tools are in the scripts folder.

The patch series might be regarded as the real commit history, whereas the git commit history here can be relaxing and/or having meaningless commit messages.

Image builds use the pinned `nixpkgs-unstable` revision in `flake.lock` and
`work/mobile-nixos/npins/sources.json` (exported in the patch series). Keep
both pins in sync when updating. The system package set uses Qt 6.12.0 from
unstable. Hoki's Qt package definitions are vendored from `staging-26.05` at
revision `3da11a55bdd37955b63cc4182ff789eeaa152329` (Qt 6.11.3) under
`work/mobile-nixos/overlay/vendor/qt-6.11`. They use unstable for dependencies
and toolchains. ARM Qt artifacts are not covered by the binary cache and must
be built locally.
The Hoki and Beluga vendor kernels separately retain their old nixpkgs pin
for GCC 8, which is unavailable in the main package set.

Build the AsteroidOS image from the patched checkout:

```sh
nix-build work/mobile-nixos/examples/asteroid --argstr device fossil-hoki -A outputs.default
```

## Status

For hoki (Fossil Gen 6):

+ [x] mobile-nixos stage1
+ [x] asteroid os splash
+ [ ] asteroid os launcher

## Devices, Linux Kernel

+ fossil-hoki running kernel 4.14.x EOL, but openela : <https://github.com/openela/kernel-lts/tree/linux-4.14.y>
+ Planned: pixel watch 2, supported kernel

For devices running EOL kernel, it is equivalent to every processes having root permissions.


## TODO

+ move hoki hardcoded partitions to better places
+ instead of linking /usr/share for asteroid os launcher, patch them to use nix store path.

## LLM Policy

LLM usage shall be discouraged when resources are available.
