# Matawaa - Smartwatch Issue Tracker & Remaining TODOs

This document catalogs and tracks remaining hardware, runtime, packaging, and architecture issues requiring physical hardware testing, on-device debugging, or ongoing vendor HAL reverse-engineering.

---

## 1. On-Device Issues Requiring Physical Hardware Verification

### 1.1 MCE Battery Level Readout (`-1%` Display Indicator)
* **Observed on:** Fossil Gen 6 (`fossil-hoki`)
* **Symptom:** The watchface battery indicator shows `-1%`, even though `/sys/class/power_supply/battery/capacity` in sysfs correctly reports battery status (e.g. 100%).
* **Technical Context:**
  * AsteroidOS userland interfaces with battery information via Mode Control Entity (MCE) over D-Bus (`com.nokia.mce`).
  * MCE loads `battery-udev.so` (`modules/battery-udev.c`), listening for `power_supply` subsystem events using `libudev`.
  * `battery-udev.c` specifically looks for udev properties `POWER_SUPPLY_CAPACITY` (`PROP_CAPACITY`) and `POWER_SUPPLY_STATUS` (`PROP_STATUS`).
* **Remaining Verification & Resolution Steps:**
  1. Connect to watch via SSH: `ssh ceres@172.16.42.1`.
  2. Query udev database entry: `udevadm info -p /sys/class/power_supply/battery`.
  3. Query MCE state: `mcetool --dump-state | grep -i battery`.
  4. Test triggering udev coldboot event: `udevadm trigger --action=change --subsystem-match=power_supply`.
  5. If udev lacks `POWER_SUPPLY_CAPACITY`, add udev rule in `services.udev.extraRules`:
     ```udev
     SUBSYSTEM=="power_supply", ATTR{capacity}=="?*", ENV{POWER_SUPPLY_CAPACITY}="$attr{capacity}"
     SUBSYSTEM=="power_supply", ATTR{status}=="?*", ENV{POWER_SUPPLY_STATUS}="$attr{status}"
     ```

---

### 1.2 Raydium Touchscreen Input Event Verification
* **Observed on:** Fossil Gen 6 (`fossil-hoki`)
* **Remaining Verification Steps:**
  1. Boot the updated image or deploy via `./scripts/deployWatch.sh`.
  2. Verify user permissions: ensure `/dev/input/event*` devices are accessible by user `ceres` (in `input` group).
  3. Touch the display to verify watchface transitions and app launcher swipe gestures.

---

### 1.3 Hardware Composer Layer Pipe Exhaustion
* **Observed in:** Kernel `dmesg` logs on Qualcomm Snapdragon Wear 4100
* **Log message:** `msm_mdss_get_res_byname: 'vbif_nrt_phys' resource not found`, `mdss_mdp_pipe_init: no 2 type pipes available`
* **Remaining Verification & Resolution Steps:**
  * Verify whether setting `QPA_HWC_FORCE_GLES=1` (set in `20-device.conf`) completely delegates non-root layers to GPU composition.
  * If pipe exhaustion still occurs during multi-app or video playback, evaluate capping the number of HW composer layers in `qt6-qpa-hwcomposer-plugin`.

---

### 1.4 Oppo Watch (`oppo-beluga`) Touch Calibration & Orientation
* **Observed on:** Oppo Watch 46mm (`oppo-beluga`)
* **Remaining Verification Steps:**
  * Flash `oppo-beluga` fastboot images and confirm touch coordinates match visual UI buttons.
  * If touch is offset by 90/180/270 degrees, configure `QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS=rotate=90` (or `invertx`, `inverty`) in `devices/oppo-beluga/default.nix`.

---

### 1.5 Audio Routing & Hardware Mixer Profiles (NXP TFA98xx & Mic)
* **Observed on:** Fossil Gen 6 (`fossil-hoki`)
* **Remaining Verification Steps:**
  * Test speaker audio playback:
    ```sh
    aplay -D default /run/current-system/sw/share/sounds/asteroid/stereo/bell.wav
    ```
  * Test microphone recording:
    ```sh
    arecord -D default -f cd -d 5 /tmp/test-mic.wav && aplay /tmp/test-mic.wav
    ```
  * Build full ALSA Use Case Manager (UCM) or PulseAudio profile configuration files for voice call routing.

---

## 2. Upstream Architecture & Long-Term Roadmap

### 2.1 Mainline Linux Kernel Bringup for Snapdragon Wear 4100 (`fossil-hoki-mainline`)
* **Remaining Hardware Verification & Bringup Work:**
  * Upstream DSI panel driver (Command Mode) for the 416x416 AMOLED display (transition from simplefb to native dynamic DRM modesetting).
  * Native DRM touch input binding for Raydium RM69330 I2C controller.
  * PMIC battery fuel gauge (BMS) and charger drivers.

---

### 2.2 WebKitGTK / WPE WebKit Sandbox Hardening
* **Remaining Work:**
  * Investigate if a tailored seccomp filter configuration or unprivileged namespace backport can enable sandboxed WebProcess execution on Linux 4.14 kernels without requiring `WEBKIT_FORCE_SANDBOX=0`.
