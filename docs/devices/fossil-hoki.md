# Fossil Gen 6 (`fossil-hoki`) Device Notes

The **Fossil Gen 6** (codename `hoki`) is the primary reference smartwatch platform for NixOS for Smartwatches. It features Qualcomm Snapdragon Wear 4100+ silicon, a 416×416 round AMOLED display, and a digital rotating crown.

---

## Hardware Specifications

| Component | Specification | Notes |
| :--- | :--- | :--- |
| **SoC** | Qualcomm Snapdragon Wear 4100+ (SDA429W) | 4× ARM Cortex-A7 @ 1.95 GHz, Adreno 504 GPU |
| **Memory** | 1 GB LPDDR3 | Shared system RAM |
| **Storage** | 8 GB eMMC 5.1 | Partitioned for A/B boot and large `userdata` |
| **Display** | 1.28″ Round AMOLED (416×416, ~326 ppi) | 60 Hz refresh, Always-On Display (AOD) ambient mode |
| **Touch** | Capacitive multi-touch | Handled via `evdevtouch` Qt input plugin |
| **Controls** | Digital rotating crown + 2 hardware push-buttons | Crown mapped to rotary encoder input |
| **Haptics** | Linear Resonant Actuator (LRA) | Controlled via `ff-memless` force-feedback driver |
| **Wireless** | Wi-Fi 802.11 b/g/n + Bluetooth 5.0 LE / BR/EDR | BlueZ dual-mode configuration (`ControllerMode = dual`) |
| **Sensors** | Heart rate (PPG), Accelerometer, Gyroscope, Compass, Off-body | Calibrated via `/persist` partition |

---

## Partition Architecture & Mounts

The Fossil Gen 6 utilizes Qualcomm A/B partition architecture on its internal eMMC:

| Partition / Partlabel | Mount Point | Filesystem | Mount Flags | Description |
| :--- | :--- | :--- | :--- | :--- |
| `boot_a` / `boot_b` | — | Android Boot v0 | — | Linux 4.14 kernel with appended `sda429-hoki.dtb` + mobile-nixos stage-1 initrd |
| `userdata` | `/` | ext4 | rw | Target for `system.img` (`LABEL=NIXOS_SYSTEM`). Automatically resized on first boot. |
| `persist` | `/persist` | ext4 | nofail | Optical sensor calibration, board serials, and battery fuel-gauge profiles |
| `modem` | `/vendor/firmware_mnt` | vfat | ro, nofail | Qualcomm Hexagon DSP firmware and Wi-Fi/GNSS binaries |
| `bluetooth` | `/vendor/bt_firmware` | vfat | ro, nofail | Broadcom / Qualcomm Bluetooth controller firmware |

> [!IMPORTANT]
> The `/persist`, `/vendor/firmware_mnt`, and `/vendor/bt_firmware` mounts use `nofail` so that unformatted partitions or read-only stages do not block booting into emergency shell.

---

## Fastboot Key Combinations

- **Enter Fastboot Mode from Power-Off**: Place watch on charging puck, then hold down the **middle crown button + bottom push-button** simultaneously until the fastboot bootloader screen appears.
- **Force Reboot / Rescue from Hang**: If the watch hangs during kernel or early userland experimentation, hold down the **middle crown button + bottom push-button** for ~10 seconds to force a hardware reset directly back into the fastboot bootloader.
- **Enter Fastboot from ADB**:
  ```bash
  adb reboot bootloader
  ```

---

## Flashing Instructions

### Method 1: Fastboot with Native Sparse Image (Recommended)

The generated `result/system.img` is automatically formatted as a native Android sparse filesystem image (`img2simg`). This avoids fastboot client-side chunking errors (`Invalid sparse file format at header magic` / `Error reading sparse file`) and skips empty blocks to speed up transfers over USB pogo pins:

```bash
# 1. Verify fastboot communication:
fastboot devices

# 2. Flash kernel and stage-1 initramfs to both A/B slots:
fastboot flash --slot=all boot result/boot.img
# (Alternatively, run the generated ./result/flash-critical.sh)

# 3. Flash root filesystem into userdata (recommended for full eMMC space):
fastboot flash userdata result/system.img

# 4. Optional: clear stale Android cache if migrating from Wear OS:
fastboot format cache

# 5. Reboot into NixOS:
fastboot reboot
```

---

### Method 2: Alternative Flashing via TWRP Recovery (Untested / Community Method)

> [!WARNING]
> **Experimental / Untested**: Flashing via TWRP recovery on `fossil-hoki` is a community-developed workaround and is currently **untested** in our primary pipeline. Use the native sparse fastboot method (Method 1) whenever possible.

The magnetic charging cradle on the Fossil Gen 6 can be physically sensitive; slight shifts during multi-minute writes can reset the USB interface (`Write to device failed`, `Status read failed (No such device)`).

To guarantee successful flashing over flaky connections without starting over on every drop, use the included **`bin/resilient-flash`** tool:
- **Chunked Writes (Default 16 MB)**: Writes disk images in small blocks via `dd of=<partition> bs=1048576 seek=<offset>` so dropped connections interrupt only seconds of transfer.
- **In-Memory Resume**: Tracks verified chunks in process memory, eliminating disk cache permission traps when using `sudo adb`.
- **Hardware Dual-Tier SHA256 Verification**: Calculates and verifies cryptographic checksums directly on the watch eMMC flash for every chunk, followed by an end-to-end full partition verification after buffers are synced.
- **Auto-Recovery on Drop**: When USB disconnects or times out, immediately resets the ADB daemon (`adb kill-server`), settles for 10s, and retries the interrupted block directly without blocking on hung `wait-for-device` probes.
- **Auto Sparse Unsparsing**: Automatically unpacks native Android sparse images on the host via `simg2img` without wasting watch memory.

1. **Boot TWRP temporarily via fastboot** (does not overwrite stock recovery):
   ```bash
   fastboot boot twrp_hoki.img
   ```

2. **Run Resilient Flash**:
   ```bash
   # Flashing by passing output directory directly (auto-detects system.img & boot.img):
   ./bin/resilient-flash result --reboot

   # Or providing device name and image files in any order:
   ./bin/resilient-flash fossil-hoki result/boot.img result/system.img --reboot

   # If host permissions require sudo for adb:
   ./bin/resilient-flash result --sudo --reboot

   # Optional flags:
   #   --timeout 90        Custom chunk write timeout in seconds (default: 60s)
   #   --chunk-size 8      Smaller chunk size in MB for extremely flaky connections
   #   --no-verify         Skip SHA256 readback verification for maximum speed
   #   --no-boot           Skip flashing boot partition
   ```

#### Technical Notes & Recovery Quirks
- **Why Fastboot Cannot Resume**: The Fastboot protocol (in LittleKernel bootloader) is stateless and writes directly to an in-memory buffer before flashing. It has no seek or offset parameter. If USB drops, the buffer is purged and the endpoint resets. TWRP boots full Linux userspace with direct `/dev/block/...` access, making seek-based block writes possible.
- **`conv=notrunc` Disabled in Recovery `dd`**: Android recovery `busybox`/`toybox` often compiles out `conv` support (`dd: conv option disabled`). Because Linux block special devices (`/dev/block/...`) have a fixed hardware geometry and cannot be truncated by the kernel anyway, `conv=notrunc` must be omitted.
- **Byte Multiples vs. Suffixes**: Minimal recovery `toolbox` does not parse unit suffixes like `1M` or `status=none`. All offsets and block sizes are passed as exact integer bytes (`bs=1048576`), and stderr is routed via standard POSIX `2>/dev/null`.
- **Avoiding `adb wait-for-device` Hangs**: Dropped packets on Linux ADB USB sockets often leave the host daemon wedged. Bouncing `adb kill-server` and giving a fixed 10-second bus settlement delay before attempting direct writes avoids infinite hangs.

*(Manual fallback: `simg2img result/system.img /tmp/system_raw.img && dd if=/tmp/system_raw.img bs=1M status=progress | adb shell -T "cat > /dev/block/bootdevice/by-name/userdata && sync"`)*

---

## Compositor & Display Architecture

- **Compositor**: `asteroid-launcher` runs as a systemd user service under user `ceres`:
  ```bash
  systemctl --user status asteroid-launcher
  ```
- **Platform Plugin**: Qt 6 uses `hwcomposer` (`QT_QPA_PLATFORM=hwcomposer`, `EGL_PLATFORM=hwcomposer`) to talk to the Qualcomm Android HAL (`libhybris`).
- **Touch Input**: Launched with `-plugin evdevtouch --systemd`.
- **Rotary Crown**: Handled as evdev axis/key events in `asteroid-launcher`.

---

## Debugging & Remote Shell Access

When booted, the watch exposes a USB CDC Ethernet interface (`192.168.2.15`):

```bash
# Configure host network:
sudo ip addr add 192.168.2.14/24 dev usb0
sudo ip link set usb0 up

# SSH to the watch:
ssh root@192.168.2.15

# Inspect compositor logs:
journalctl --user -u asteroid-launcher -f

# Inspect kernel dmesg:
dmesg | grep -iE "msm|drm|bluetooth|wlan|touch"
```

### Stage-2 boot capture

The stage1-pause-debug image pauses in stage-1 before switching root and exposes
`172.16.42.1` over USB networking. Connect with `telnet 172.16.42.1` (the
stage-1 root password for SSH is `root`), then start a persistent kernel log
and resume:

```sh
mkdir -p /mnt/root/dbg
cat /proc/kmsg > /mnt/root/dbg/dmesg.log 2>&1 &
( while :; do sync; sleep 10; done ) >/dev/null 2>&1 &
/bin/continue-boot
```

If stage-2 still ends in a black screen, reboot back into stage-1 (the hold is
enabled on every boot in the stage1-pause-debug image), reconnect, and read the captured
log:

```sh
cat /mnt/root/dbg/dmesg.log
```

Look for `systemd[1]`, `statx`, `pidfd`, `close_range`, `Freezing execution`,
and `status=202/FDS`. The current image includes the systemd 262 old-kernel
fallbacks for mountpoint, faccessat, statx, pidfd, and close_range; capture the
new tail if one of those errors is still present.

---

## Kernel Baseline and Security Status

`fossil-hoki` currently runs the vendor Android 4.14 kernel from
[`fossil-engineering/kernel-msm-fossil-cw`](https://github.com/fossil-engineering/kernel-msm-fossil-cw),
branch `fossil-android-msm-hoki-lw1.2-4.14`, commit
`c0b4c201f2d5a641defe19958a9b4c16f40d866b`. The AsteroidOS `meta-hoki` kernel
recipe pins the same revision. The vendor branch's last commit is from
2023-03-01; no newer vendor branch is available.

Upstream Linux 4.14 reached end-of-life on 2024-01-10, with 4.14.336 as the
final release. The vendor tree is frozen at 4.14.206 plus Qualcomm/Android
changes, with incremental 4.14.207 and 4.14.208 stable updates applied. It still
does not include later upstream stable or CVE backports. The Red Hat OpenShift
4.14 EUS lifecycle is unrelated to the Linux 4.14 kernel and does not patch this
tree.

### Attempted 4.14 stable update

We tried three stable updates on top of the vendor tree:

- OpenELA `4.14.206` -> `4.14.357`
- kernel.org `4.14.206` -> `4.14.336`
- kernel.org `4.14.206` -> `4.14.208` (incremental `incr/` patches)

The two latest-tree updates required resolving hundreds of vendor conflicts. The
resulting trees failed to build on repeated subsystem/API and shared-header
mismatches, including binder/security hooks, `net/socket`, perf/trace,
ext4/f2fs/fscrypt, sched/bpf/IMA, zram/net, and random/crypto/net. Taking the
vendor implementation for each failing subsystem would revert most of the
stable security changes, so neither update was merged.

The first `4.14.207` attempt used `patch-4.14.207.xz`, which is a full
`4.14.0` -> `4.14.207` diff rather than the incremental patch; it produced
9,160 `Reversed (or previously applied)` hunks and failed. The correct
incremental patch is `incr/patch-4.14.206-207.xz` (37K). It applies after
adapting the syncookies `tcp_select_initial_window()` call to the vendor
`sock_net()` argument and dropping the perf core/header and Intel PT diffs
already present in the vendor tree. The `4.14.207` kernel and debug image build
successfully. The `incr/patch-4.14.207-208.xz` patch then applies cleanly, so
the current kernel is `4.14.208`.

A 4.14.208 debug image is produced; no 4.14.336 image was produced. Larger
whole-tree stable updates remain impractical for this vendor fork.

### Security implication

Treat this kernel as an unmaintained 4.14 vendor tree, not a fully
security-patched kernel. For security-sensitive use, prefer targeted CVE
backports on 4.14.208 or a proper subsystem-level port to a maintained kernel.
A file-level stable diff is not sufficient for this vendor fork.

---

## Kiwix Offline Wikipedia & Reference Reader

The watch environment includes Kiwix (`asteroid.apps.kiwix`) paired with the AsteroidOS smartwatch browser. To load offline encyclopedias or books:

1. Download `.zim` files from [library.kiwix.org](https://library.kiwix.org/) (e.g. *Wikipedia Simple English*, *Wiktionary*, or *Project Gutenberg*).
2. Transfer the `.zim` file to the watch over USB or SSH:
   ```bash
   # Via ADB:
   adb push wikipedia_en_simple_all_nopic_2024.zim /var/lib/kiwix/

   # Via SSH over USB networking:
   scp wikipedia_en_simple_all_nopic_2024.zim root@192.168.2.15:/var/lib/kiwix/
   ```
3. Open **Kiwix** from the AsteroidOS app drawer or tap **Kiwix (Offline)** on the browser home portal. Articles and full-text search are instantly accessible directly on the wrist.

