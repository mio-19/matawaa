# Hoki ambient display and MCU timepiece mode

These are separate display paths. Normal ambient mode keeps the NixOS session
available. MCU timepiece mode shuts Linux down; it is not a suspend/wake watchface.

## Normal ambient mode

Hoki uses `QPA_HWC2_DOZE_UPDATE=1` to submit ambient frames in HWC2 `DOZE`, then
restore `DOZE_SUSPEND`. Unlike upstream's `QPA_HWC2_FORCE_DOZE_UPDATE`, it does
not request full `ON` for each frame. The plugin waits for the current present
fence before restoring suspend and restores the mode on error exits as well.
A concurrent interactive wake cancels that restoration.

The legacy ON workaround remains available for other HALs. No automatic ON
fallback is used by the new mode: rejected low-power transitions are logged.
The Hoki user-service environment sets the new flag on OTA upgrades as well as
new images; existing `/var/lib/environment/compositor` files can survive an OTA.

Upstream ambient implementation:
[meta-asteroid ambient patch](https://github.com/AsteroidOS/meta-asteroid/blob/c84c0bbd731f9dfa3b04295bac239dd7fa64c722/recipes-qt/qt6/qt6-qpa-hwcomposer-plugin/0001-Add-ambient-mode-display-support.patch).

## MCU timepiece mode

The package pins the upstream author's Hoki branch of
[asteroid-coprocessor PR 3](https://github.com/MagneFire/asteroid-coprocessor/pull/3)
at `976d3432347e2f67d23e3de7baac60a852ae823f`. This is an upstream draft,
not merged MCU AOD support. It uses the existing Sidekick HIDL
service and ships upstream's clock assets and user services. The only source
adaptation recognizes Mobile NixOS's `fossil-hoki` machine name as upstream `hoki`.

The kernel-timezone helper is taken unchanged from
[meta-asteroid PR 332](https://github.com/AsteroidOS/meta-asteroid/pull/332), pinned
at `3ca9e1e419fa8db58adb0c6bfd55a260e861b51c`. It sets the kernel offset read by
Bionic before Android init, on timezone changes and hourly for DST. The timer
avoids the resume-triggered `OnClockChange` behavior noted in upstream review.

From the watch's **ceres user session**, inspect support with:

```sh
busctl --user get-property org.asteroid.SecondDisplay /Display \
  org.asteroid.SecondDisplay.Display Capabilities
asteroid-seconddisplay --sync-time
```

Capabilities `3` means time synchronization and timepiece mode. To explicitly
enter the MCU clock and power Linux off:

```sh
asteroid-seconddisplay --enter-timepiece
```

This disconnects SSH and stops apps. Return to Linux requires a hardware boot;
this branch does not implement a reversible MCU AOD handoff. Even
`--prepare-timepiece` reloads BG firmware, so it is not a harmless readiness probe.
Nothing enters or prepares timepiece mode automatically on idle or suspend.

## Device validation, 2026-11-10

The ARMv7 coprocessor package, timezone helper, graphics plugin and complete Hoki
system cross-build successfully. All 49 patches replay without three-way fallback
and produce the same tree as the work checkout and Nix-patched source. Static
linkage checks pass for all 10 ELF paths matching the new daemon, helper and
graphics plugin. The timezone/Android-init service ordering passes
`systemd-analyze verify`. On the watch via SSH port 2222:

- The daemon connects to `vendor.google_clockwork.sidekickgraphics@1.2::ISidekickGraphics/default`.
- Sidekick reports capabilities `0x1102000b`, a 412x412 display and 120651 bytes
  available; the daemon exposes capabilities `3` and time synchronization succeeds.
- The timezone helper changes the kernel offset from UTC to -660 minutes west
  (Canberra daylight time), without setting the system clock.
- Ambient refreshes at 11:31 and 11:32 accept HWC2 power mode `1` (`DOZE`) and
  restore `DOZE_SUSPEND`; unlike the baseline they generate no panel UNBLANK
  events. The launcher remains active without restarts.

These logs establish accepted transitions and removal of the full-ON refresh
path. Visual confirmation of clock advancement and absence of flashes is still
needed. The MCU firmware preparation/power-off handoff has not been exercised.
