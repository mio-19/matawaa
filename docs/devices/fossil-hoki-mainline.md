# Fossil Gen 6 (hoki) mainline draft

**Status: DRAFT. Expected not to boot.**

This target is a skeleton for an hoki mainline port:

- kernel: Linux 6.18 LTS mainline (`linuxPackages_6_18.kernel`), armv7l
- userspace and stage 1: `armv7l-linux` (the SoC cores are Cortex-A53)
- hardware description: standalone device definition; it imports only
  `../families/asteroidos.nix` and does not import `fossil-hoki`
- no vendor 4.14 kernel or vendor kernel patches
- the flattened vendor `sda429-hoki.dts` is added to the mainline qcom DTS
  directory and appended to the boot image as `dtbs/sda429-hoki.dtb`

Mainline hoki support is not complete. Display, touch, modem, WLAN, audio, and
other vendor peripherals still need mainline drivers or DT bindings, so this
target should not be flashed to a watch for daily use. It is marked
`best-effort` in the device metadata and is intended for bring-up work only.

Build (the command resolves the draft device by directory name):

```sh
nix-build examples/asteroid --argstr device fossil-hoki-mainline -A outputs.default
```

The generated image now builds with the vendor DTB, but it is not expected to
reach the launcher until the mainline peripheral drivers are ported.
