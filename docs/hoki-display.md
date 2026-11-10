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

MCE's AsteroidOS ambient patch reduces both timeouts around `LPM_OFF` from five
seconds to one. Hoki now restores AsteroidOS's five-second defaults, giving the
ambient and proximity blanking transitions the upstream dwell time instead of
the one-second sequence that coincided with the reported black-screen event.

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
system cross-build successfully. All 50 patches replay without three-way fallback
and produce the same tree as the work checkout and Nix-patched source. Static
linkage checks pass for 25 ELF paths covering the new daemon, helper, graphics
plugin and keepalive examples. The timezone/Android-init service ordering passes
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

Deployment also exposed an earlier qmake packaging error: keepalive's three
example binaries were installed under `$out/nix/store/<native-qt>/bin`, outside
normal stripping/fixup directories. Their directory names and unstripped debug
info retained native Qt and the cross compiler. The examples now install in
`$out/bin`; normal Nix fixups remove their debug info and retain the target runtime libraries.
The package rejects references to native Qt and the compiler to catch regressions.

With that correction, the complete system closure decreases from 2.5 GiB to
1.8 GiB and no longer depends on native Qt/ICU or the cross-binutils package
identified during deployment. All three examples remain ARM executables in
`bin`, with no `.debug_*` sections or nested store-prefix directory.

The corrected system was deployed through SSH port 2222 using `boot` activation
and rebooted successfully into
`/nix/store/yvrfvwwz0r6khkr131w0ar4b9zic7359-nixos-system-nixos-26.11pre-git`.
After reboot the launcher and MCU daemon are active with zero restarts, system
and ceres-user failed-unit lists are empty, capabilities remain `3`, and MCU time
synchronization succeeds. The new graphics plugin is mapped and
`QPA_HWC2_DOZE_UPDATE=1` is present without a temporary service override. The old
ON flag may remain in persistent compositor files, but the new DOZE flag takes
precedence. The timezone helper sets `0 -> -660` during boot before Android init.

A post-reboot wake/sleep cycle succeeds. The 11:59 ambient refresh uses DOZE and
restores DOZE_SUSPEND with no UNBLANK event or launcher restart. The MCU daemon
also remains active without restarts. Temporary deployment/verification wake
locks have been released. Visual confirmation and the explicit MCU power-off
handoff remain the validation limits described above.

After the MCE timeout correction, the new system
`/nix/store/rjhn4da0w5hljjhc0sy4zh0v9f2mv0ds-nixos-system-nixos-26.11pre-git`
was staged through port 2222 and rebooted. The launcher, MCE and second-display
daemon are active without restarts. MCE remained in `LPM_ON` for about five
seconds, then entered `LPM_OFF`; the kernel logged framebuffer suspend and no
`FB_BLANK_UNBLANK` during that transition. Visual confirmation of the AOD
remaining visible through this low-power transition is still required.


The Hoki-specific MCE policy disables the `LPM_ON` to `LPM_OFF` proximity
timeout because this watch has no proximity sensor to wake it back into AOD.
Touch or the power key still wakes the interactive display. The ON-to-DIM and
DIM-to-AOD idle timers remain at their AsteroidOS defaults, so AOD begins after
normal inactivity; the watch now stays in AOD rather than going black five
seconds later. This override is Hoki-only.

The Hoki system `/nix/store/8scndwrgzqmclvc1k71sx974j13ij825-nixos-system-nixos-26.11pre-git`
was built, staged through SSH port 2222 and rebooted on 2026-11-10. MCE entered
`LPM_ON` at 13:59:56 and again at 14:01:48, with no following `LPM_OFF`; MCE
remained active without restarts. During the latter session, the camera launch
produced the reported white screen before the display dimmed at 14:01:33 and
entered AOD at 14:01:48. At 14:06 the camera process was gone and MCE was still
in AOD. A later launch captured a QML creation error: `IconButton` instances
were assigned the unsupported `icon` property, preventing the camera page from
loading. Those bindings now use AsteroidOS's `iconName` property. The corrected
package was built and deployed in `/nix/store/2m0w5gcsxsgjqhgkv5nwp5lv5a5w7k6l-nixos-system-nixos-26.11pre-git`;
a post-reboot launch showed the waiting-for-phone UI without the QML error.
The source has no translation catalog, so Qt logs a failed `en_GB` catalog
lookup; visible camera status strings are literal English and do not depend on
that catalog. A follow-up larger, bold waiting label built in
`/nix/store/afv7xd9ligj4zgr3ks2zl7x27ks7vhjm-nixos-system-nixos-26.11pre-git`,
but could not be transferred because the SSH tunnel stopped responding.
