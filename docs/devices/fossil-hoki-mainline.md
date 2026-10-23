# Fossil Gen 6 (hoki) mainline draft

**Status: DRAFT. Expected not to boot.**

This target is a skeleton for an all-AArch64 hoki port:

- kernel: Linux 6.18 LTS mainline (`linuxPackages_6_18.kernel`)
- userspace and stage 1: `aarch64-linux`
- hardware description: reuses the existing `fossil-hoki` device definition
- no vendor 4.14 kernel, vendor patches, or vendor boot DTB

Mainline hoki support is not complete. Display, touch, modem, WLAN, audio, and
other vendor peripherals still need mainline drivers or DT bindings, so this
target should not be flashed to a watch for daily use. It is marked
`best-effort` in the device metadata and is intended for bring-up work only.

Build (the command resolves the draft device by directory name):

```sh
nix-build examples/asteroid --argstr device fossil-hoki-mainline -A outputs.default
```

The generated image is not expected to reach the launcher until the mainline
device tree and peripheral drivers are ported.
