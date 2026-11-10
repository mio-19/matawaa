# Matawaa

status: early development. code not ready for review or contributing

this project aims to bring a better open source operating system experience to commercially available smartwatches. this project forks [Mobile-NixOS](https://mobile.nixos.org/) and adapt it for smartwatches by building on the existing works of [AsteroidOS](https://asteroidos.org/). this project will be able to package asteroid os with the nix package manager and improve the usability on top of asteroid os. this project will be able to implement an atomic upgrade procedure similar to NixOS; while the AsteroidOS currently does not have a good way to upgrade without losing data. this project will implement encryption based on the existing works done by mobile-nixos. Then this project will implement common smartwatches features on top of AsteroidOS, like "find my phone". this project will also develop AsteroidOS apps. For changes that make sense to upstream to AsteroidOS, this project will seek to upstream them.

Patched versions of android companion apps will be in [this repo](https://github.com/mio-19/repo)

## Development

This project is a patchset on top of [Mobile-NixOS](https://mobile.nixos.org/). tools are in the scripts folder.

The patch series might be regarded as the real commit history, whereas the git commit history here can be relaxing and/or having meaningless commit messages.

Build the AsteroidOS image from the patched checkout:

```sh
./scripts/applyPatches.sh
nix-build work/mobile-nixos/examples/asteroid --argstr device fossil-hoki -A outputs.default
```

## Devices, Linux Kernel

+ google-aurora (Pixel Watch 2): 5.15.144 vendor kernel and configuration are packaged; unverified on hardware


## TODO

+ move hoki hardcoded partitions to better places
+ asteriod os usbnet adb modes

## Device: hoki (Fossil Gen 6)

running an old version of 4.14.x 

For devices running EOL kernel, it is equivalent to every processes having root permissions.

TODO
+ at least update to openela's version : <https://github.com/openela/kernel-lts/tree/linux-4.14.y>


## LLM Policy

LLM usage (including read-only and read-write) shall be discouraged when resources are available. An LLM writes code based on false assumptions confidently.

At a bare minimum, communications shall be written by human, and code intended for other people to review shall only be submitted by human and has been reviewed by human.


