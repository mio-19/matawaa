# Matawaa - Smartwatch Issue Tracker & Remaining TODOs

This document catalogs and tracks remaining hardware, runtime, packaging, and architecture issues requiring physical hardware testing, on-device debugging, or ongoing vendor HAL reverse-engineering.

## 0. Packaging and Runtime Follow-ups

* **Fscrypt home-directory provisioning:** `modules/fscrypt.nix` exposes `user` and `policy`, but does not provision an encrypted home. Design and validate login, recovery, existing-data migration, and filesystem handling before enabling it on a device.
* **SensorFW upstream qmake build:** The pinned source provides qmake projects, but the current Nix cross setup fails their `qtConfig()` checks. Keep the working local CMake build until a cross-compilation setup can build the upstream project and its plugins correctly.
* **Cross-built QML module discovery:** Check the remaining target-tool discovery warnings against the installed QML modules on Fossil Hoki. Confirm actual imports on device before treating a warning as a missing module.

---

## 1. On-Device Issues Requiring Physical Hardware Verification

### 1.1 Hardware Composer Layer Pipe Exhaustion
* **Observed in:** Kernel `dmesg` logs on Qualcomm Snapdragon Wear 4100
* **Log message:** `msm_mdss_get_res_byname: 'vbif_nrt_phys' resource not found`, `mdss_mdp_pipe_init: no 2 type pipes available`
* **Remaining Verification & Resolution Steps:**
  * Verify whether setting `QPA_HWC_FORCE_GLES=1` (set in `20-device.conf`) completely delegates non-root layers to GPU composition.
  * If pipe exhaustion still occurs during multi-app or video playback, evaluate capping the number of HW composer layers in `qt6-qpa-hwcomposer-plugin`.

---

### 1.2 Oppo Watch (`oppo-beluga`) Touch Calibration & Orientation
* **Observed on:** Oppo Watch 46mm (`oppo-beluga`)
* **Remaining Verification Steps:**
  * Flash `oppo-beluga` fastboot images and confirm touch coordinates match visual UI buttons.
  * If touch is offset by 90/180/270 degrees, configure `QT_QPA_EVDEV_TOUCHSCREEN_PARAMETERS=rotate=90` (or `invertx`, `inverty`) in `devices/oppo-beluga/default.nix`.

---

### 1.3 Audio Routing & Hardware Mixer Profiles (NXP TFA98xx & Mic)
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

### 1.4 MSM MDSS Display Frame Commit Warnings (`ctx=0 stopped already`)
* **Observed on:** Fossil Gen 6 (`fossil-hoki`)
* **Symptom:** Kernel `dmesg` logs show repeated messages such as:
  ```
  mdss_mdp_display_commit: ctl 0 error displaying frame
  mdss_mdp_display_commit: ctx=0 stopped already
  ```
* **Technical Context:**
  * In the Qualcomm Android 4.14 downstream kernel MDSS (Mobile Display SubSystem) driver, command-mode DSI display commit callbacks signal when a frame display kick occurs while a previous commit or transfer is pending, or when frames are pushed faster than the panel refresh rate (~60Hz / 16.6ms).
  * This is benign in practice and commonly observed during high frame rate UI animations (e.g. Qt Quick scenegraph renderloop bursts) where subsequent frames trigger before the hardware TE-signal / VSYNC interval completes.
* **Remaining Verification & Resolution Steps:**
  * Confirm whether tuning VSYNC pacing or buffer wait queues in `qt6-qpa-hwcomposer-plugin` reduces log verbosity.
  * Adjust MDSS logging level or rate-limit kernel printk if dmesg buffer flooding occurs.

---

## 2. Upstream Architecture & Long-Term Roadmap

### 2.1 Mainline Linux Kernel Bringup for Snapdragon Wear 4100 (`fossil-hoki-mainline`)
* **Remaining Hardware Verification & Bringup Work:**
  * Upstream DSI panel driver (Command Mode) for the 416x416 AMOLED display (transition from simplefb to native dynamic DRM modesetting).
  * Native DRM touch input binding for Raydium RM69330 I2C controller.
  * PMIC battery fuel gauge (BMS) and charger drivers.

---

### 2.2 Mainline Linux Kernel Bringup for Snapdragon Wear 3100 (`oppo-beluga-mainline`)
* **Target Overview:**
  * Standalone pure-mainline target using modern Linux 6.18, Freedreno DRM/KMS, simple-framebuffer (402x476 squircle), ramoops pstore console logging, btrfs zstd rootfs, and USB CDC-NCM gadget networking.
* **Remaining Hardware Verification & Bringup Work:**
  * Flash experimental `oppo-beluga-mainline` fastboot images and capture earlycon serial/pstore logs.
  * Verify simple-framebuffer handoff from continuous splash region (`0x83000000`).
  * Port Visionox 402x476 command-mode DSI panel driver to upstream DRM panel subsystem.
  * Native input binding for Cypress TrueTouch Gen5 (cyttsp5) I2C touchscreen controller.

---

### 2.3 WebKitGTK / WPE WebKit Sandbox Hardening
* **Remaining Work:**
  * Investigate if a tailored seccomp filter configuration or unprivileged namespace backport can enable sandboxed WebProcess execution on Linux 4.14 kernels without requiring `WEBKIT_FORCE_SANDBOX=0`.
