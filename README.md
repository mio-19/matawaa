# Matawaa

this project aims to bring a better open source operating system experience to commercially available smartwatches. this project forks [Mobile-NixOS](https://mobile.nixos.org/) and adapt it for smartwatches by building on the existing works of [AsteroidOS](https://asteroidos.org/). this project will be able to package asteroid os with the nix package manager and improve the usability on top of asteroid os. this project will be able to implement an atomic upgrade procedure similar to NixOS; while the AsteroidOS currently does not have a good way to upgrade without losing data. this project will implement encryption based on the existing works done by mobile-nixos. Then this project will implement common smartwatches features on top of AsteroidOS, like "find my phone". this project will also develop AsteroidOS apps. For changes that make sense to upstream to AsteroidOS, this project will seek to upstream them.

Patched versions of android companion apps will be in [this repo](https://github.com/mio-19/repo)

## Development

This project is a patchset on top of [Mobile-NixOS](https://mobile.nixos.org/). tools are in the scripts folder.

The patch series might be regarded as the real commit history, whereas the git commit history here can be relaxing and/or having meaningless commit messages.

## Devices, Linux Kernel

+ fossil-hoki running kernel 4.14.x EOL, but openela : <https://github.com/openela/kernel-lts/tree/linux-4.14.y>
+ Planned: pixel watch 2, supported kernel

For devices running EOL kernel, it is equivalent to every processes having root permissions.
