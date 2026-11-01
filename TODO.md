# Matawaa - Smartwatch Issue Tracker & Remaining TODOs

This document catalogs and tracks all hardware, runtime, packaging, and architecture issues identified across development sessions (Antigravity, Codex, Reasonix, Freebuff). Issues that have enough information and can be resolved in software have been fixed and committed; the items below require physical hardware testing, on-device debugging via SSH/telnet, or ongoing vendor HAL reverse-engineering.

---

## 1. On-Device Issues Requiring Physical Hardware Verification

### 1.1 MCE Battery Level Readout (`-1%` Display Indicator)
* **Observed on:** Fossil Gen 6 (`fossil-hoki`)
* **Symptom:** The watchface battery indicator shows `-1%`, even though `/sys/class/power_supply/battery/capacity` in sysfs correctly reports battery status (e.g. 100%).
* **Technical Context:**
  * AsteroidOS userland interfaces with battery information via Mode Control Entity (MCE) over D-Bus (`com.nokia.mce`).
  * MCE loads the `battery-udev.so` plugin (`modules/battery-udev.c`), which listens for `power_supply` subsystem events using `libudev`.
  * `battery-udev.c` specifically looks for udev properties `POWER_SUPPLY_CAPACITY` (`PROP_CAPACITY`) and `POWER_SUPPLY_STATUS` (`PROP_STATUS`). If `PROP_CAPACITY` is not present as a udev property, `udevdevice_get_int_prop` returns `-1`, causing MCE to publish `battery_level = -1`.
  * In Linux sysfs, the kernel power supply driver exposes attributes like `/sys/class/power_supply/battery/capacity`, but `systemd-udevd` only populates the corresponding environment variables in `/run/udev/data/+power_supply:...` when uevents are triggered or an explicit udev rule imports them.
* **Verification & Resolution Steps on Hardware:**
  1. Connect to the watch via SSH: `ssh ceres@172.16.42.1` (or `root@172.16.42.1`).
  2. Query udev's current database entry:
     ```sh
     udevadm info -p /sys/class/power_supply/battery
     ```
  3. Query MCE's internal battery state:
     ```sh
     mcetool --dump-state | grep -i battery
     ```
  4. Test triggering a udev coldboot event for power supplies:
     ```sh
     udevadm trigger --action=change --subsystem-match=power_supply
     ```
  5. If udev lacks `POWER_SUPPLY_CAPACITY`, add a rule in `services.udev.extraRules`:
     ```udev
     SUBSYSTEM=="power_supply", ATTR{capacity}=="?*", ENV{POWER_SUPPLY_CAPACITY}="$attr{capacity}"
     SUBSYSTEM=="power_supply", ATTR{status}=="?*", ENV{POWER_SUPPLY_STATUS}="$attr{status}"
     ```

---

### 1.2 Raydium Touchscreen Input Event Verification
* **Observed on:** Fossil Gen 6 (`fossil-hoki`)
* **Symptom:** Kernel logs show Raydium I2C touch coordinates in `dmesg`, but the Asteroid launcher UI was not responding to touch interactions.
* **Fix Applied:**
  * In `devices/fossil-hoki/default.nix`, removed the incorrect hardcoded `QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS=/dev/input/by-path/platform-78b8000.i2c-event` from `20-device.conf`.
  * Upstream AsteroidOS `meta-hoki` does not set this parameter; leaving it unset allows Qt's `evdevtouch` plugin to automatically scan all `/dev/input/event*` devices using capability masks (`ABS_MT_POSITION_X` / `ABS_MT_POSITION_Y`), making touch discovery robust regardless of by-path symlink naming.
* **Verification Steps on Hardware:**
  1. Boot the updated image or deploy via `./scripts/deployWatch.sh`.
  2. Verify user `ceres` permissions: check that `ls -l /dev/input/event*` is group `input` (`0660`) and user `ceres` is in the `input` group.
  3. Touch the display to verify watchface transitions and app launcher swipe gestures.
  4. Note on physical testing: Ensure the watch is held firmly in its charging dock so that screen taps do not dislodge the pogo-pin USB connection.

---

### 1.3 Hardware Composer Layer Pipe Exhaustion
* **Observed in:** Kernel `dmesg` logs on Qualcomm Snapdragon Wear 4100
* **Log message:** `msm_mdss_get_res_byname: 'vbif_nrt_phys' resource not found`, `mdss_mdp_pipe_init: no 2 type pipes available`
* **Technical Context:**
  * The Qualcomm MDSS MDP (Mobile Display Subsystem) hardware provides a limited number of hardware overlay pipes (VIG, RGB, and DMA pipes).
  * When Qt's HWComposer plugin requests dedicated hardware composition planes for too many active QML layers or video views simultaneously, the MDP driver exhausts type-2 pipes.
* **Verification & Resolution Steps:**
  * Verify whether setting `QPA_HWC_FORCE_GLES=1` (already set in `20-device.conf`) completely delegates all non-root layers to OpenGL ES composition by the GPU.
  * If pipe exhaustion still occurs during multi-app or video playback, evaluate capping the number of HW composer layers in `qt6-qpa-hwcomposer-plugin`.

---

### 1.4 Oppo Watch (`oppo-beluga`) Touch Calibration & Orientation
* **Observed on:** Oppo Watch 46mm (`oppo-beluga`)
* **Technical Context:**
  * Beluga uses a 1.91-inch flexible AMOLED (402x476 resolution) with an Synaptics touch controller.
  * Depending on the hardware orientation relative to the display controller, Qt's `evdevtouch` plugin may require calibration matrix or rotation parameters.
* **Verification Steps on Hardware:**
  * Flash `oppo-beluga` fastboot images and confirm touch coordinates accurately match visual UI buttons.
  * If touch is offset by 90/180/270 degrees, configure `QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS=rotate=90` (or `invertx`, `inverty`) in `devices/oppo-beluga/default.nix`.

---

### 1.5 Audio Routing & Hardware Mixer Profiles (NXP TFA98xx & Mic)
* **Observed on:** Fossil Gen 6 (`fossil-hoki`)
* **Technical Context:**
  * Sound card 0 connects to the Qualcomm audio DSP (QDSP6) and an external NXP TFA98xx amplifier.
  * The `audio-routing-hoki` systemd service configures initial DAI link mixer controls (`QUAT_MI2S_RX Audio Mixer MultiMedia1` and `DEC1 MUX -> DMIC1`).
* **Verification Steps on Hardware:**
  * Test speaker audio playback:
    ```sh
    aplay -D default /run/current-system/sw/share/sounds/asteroid/stereo/bell.wav
    ```
  * Test microphone voice recording:
    ```sh
    arecord -D default -f cd -d 5 /tmp/test-mic.wav && aplay /tmp/test-mic.wav
    ```
  * Build full ALSA Use Case Manager (UCM) or PulseAudio profile configuration files for voice call routing.

---

## 2. Upstream Architecture & Long-Term Roadmap

### 2.1 Mainline Linux Kernel Bringup for Snapdragon Wear 4100 (`fossil-hoki-mainline`)
* **Current status:**
  * Complete pure-mainline device target defined at `devices/fossil-hoki-mainline/default.nix`.
  * Packaged Linux 6.18 LTS kernel with structured configuration (`CONFIG_ARCH_QCOM`, `CONFIG_DRM_MSM`, `CONFIG_FB_SIMPLE`, `CONFIG_ARM_APPENDED_DTB`, `CONFIG_USB_CONFIGFS_*`, `CONFIG_PSTORE_*`).
  * Structured Device Tree source (`sda429-hoki.dts`) compiled with early `simple-framebuffer` (416x416 32bpp) splash handoff, `ramoops` pstore memory carveout (`0x9ff00000 0x100000`), `blsp1_uart2` console (`ttyMSM0`), and `gpio-keys` button mappings.
  * Freedreno Mesa DRM/KMS graphics stack configured with Qt EGLFS KMS integration (`QT_QPA_PLATFORM=eglfs`, `QT_QPA_EGLFS_INTEGRATION=eglfs_kms`).
  * CDC-NCM USB gadget networking with stage-2 SSH (`172.16.42.1`) enabled for remote debugging.
  * Flake outputs (`allDevices`, `nixosConfigurations`, `deploy.nodes`) fully registered and evaluated.
  * CI workflow (`.github/workflows/build-smartwatch-images.yml`) updated with `fossil-hoki-mainline` in the build matrix for automated CI builds and Cachix caching.
* **Remaining Hardware Verification & Bringup Work:**
  * Upstream DSI panel driver (Command Mode) for the 416x416 AMOLED display (to transition from simplefb to native dynamic DRM modesetting).
  * Native DRM touch input binding for Raydium RM69330 I2C controller.
  * PMIC battery fuel gauge (BMS) and charger drivers.

### 2.2 WebKitGTK / WPE WebKit Sandbox Hardening
* **Current status:**
  * Wearable kernels (3.10, 3.18, 4.14) lack unprivileged user namespace support or have restrictions that cause WebKit's `bwrap` bubblewrap sandbox to fail on startup.
  * Currently running with `WEBKIT_FORCE_SANDBOX=0` to allow the AsteroidOS web browser to launch and render web pages.
* **Remaining Work:**
  * Investigate if a tailored seccomp filter configuration or unprivileged namespace backport can enable sandboxed WebProcess execution on Linux 4.14.


