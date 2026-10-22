# AsteroidOS Component Separation & Modifications in Matawaa

This document outlines the clear boundary between upstream **AsteroidOS** components and the custom adaptations, enhancements, and new applications developed for **Matawaa**.

---

## 1. Overview of Upstream AsteroidOS

[AsteroidOS](https://asteroidos.org/) is an open-source Linux-based operating system designed for smartwatches, originally developed by Florent Revest. Upstream AsteroidOS relies on OpenEmbedded/Yocto recipes to build a minimal environment on top of libhybris and Android kernel forks. Its user experience is powered by Qt and QML.

In Matawaa, we package AsteroidOS natively as a NixOS desktop environment and service layer that runs on standard Linux kernels as well as vendor kernels through Mobile-NixOS.

---

## 2. Upstream AsteroidOS Components (Preserved & Packaged)

The following components are packaged directly from upstream AsteroidOS git repositories with minimal adaptations necessary to compile and run in a Nix sandbox:

### Core Middleware & Shell
| Component | Upstream Repository | Purpose in AsteroidOS |
|-----------|---------------------|-----------------------|
| `libasteroid` | `AsteroidOS/libasteroid` | Core C++/Qt library providing system abstractions and data models |
| `qml-asteroid` | `AsteroidOS/qml-asteroid` | QML components and visual styling for round and square smartwatch displays |
| `asteroid-launcher` | `AsteroidOS/asteroid-launcher` | Main compositor and shell (watchfaces, notification center, quick settings, app drawer) |
| `asteroid-btsyncd` | `AsteroidOS/asteroid-btsyncd` | Bluetooth Low Energy daemon for phone notification and data synchronization |
| `asteroid-session` | `AsteroidOS/asteroid-session` | Systemd user session configuration, environment hooks, and startup sequence |

### Standard Applications
| Application | Upstream Repository | Notes |
|-------------|---------------------|-------|
| `asteroid-alarmclock` | `AsteroidOS/asteroid-alarmclock` | Clock, alarms, and timed wakeups |
| `asteroid-calculator` | `AsteroidOS/asteroid-calculator` | Touch-optimized calculator |
| `asteroid-calendar` | `AsteroidOS/asteroid-calendar` | Calendar and event viewer synced via Bluetooth |
| `asteroid-compass` | `AsteroidOS/asteroid-compass` | Hardware magnetometer compass |
| `asteroid-flashlight` | `AsteroidOS/asteroid-flashlight` | Fullscreen bright white backlight utility |
| `asteroid-heartrate` | `AsteroidOS/asteroid-heartrate` | Photoplethysmography (PPG) pulse reader |
| `asteroid-music` | `AsteroidOS/asteroid-music` | Media controller / local audio playback |
| `asteroid-settings` | `AsteroidOS/asteroid-settings` | System preferences (brightness, display timeout, Bluetooth, time) |
| `asteroid-stopwatch` | `AsteroidOS/asteroid-stopwatch` | Precision chronometer |
| `asteroid-timer` | `AsteroidOS/asteroid-timer` | Countdown timer with haptic vibration alerts |
| `asteroid-weather` | `AsteroidOS/asteroid-weather` | Weather forecast viewer |

### Community Applications
| Application | Upstream Repository | Purpose |
|-------------|---------------------|---------|
| `beatfork` | `AsteroidOS/beatfork` | Wearable audio and haptic metronome |
| `asteroid-map` | `AsteroidOS/asteroid-map` | Vector and raster tile map viewer using OpenStreetMap / CoMaps |
| `asteroid-weatherfetch` | Community | CLI and GUI weather fetching utility |
| `twenty48` | Community | 2048 puzzle game |

---

## 3. Matawaa Modifications & Enhancements to Upstream

Matawaa introduces several major architectural improvements, hardware drivers, and new applications that are not part of upstream AsteroidOS:

### A. Rotary Crown & Hardware Bezel Scrolling
* **Upstream**: AsteroidOS launcher and QML controls rely exclusively on touch swipes (`MouseArea` / `PinchArea`).
* **Matawaa**: Integrated Linux `EV_REL` / `REL_WHEEL` and `REL_DIAL` input events into `asteroid-launcher` and `qml-asteroid`. Physical rotating crowns (such as on the Fossil Gen 6, Montblanc Summit, and TicWatch) scroll vertically through app lists, dismiss notifications, and adjust system sliders without obscuring the screen with fingers.

### B. Live Viewfinder Remote Camera (`asteroid-camera`)
* **Upstream**: The original AsteroidOS camera app functions solely as a remote Bluetooth trigger button.
* **Matawaa**: Implemented a real-time MJPEG/RTSP video streaming viewfinder ([camerastreamview.cpp](file:///overlay/asteroidos/apps/camera/camerastreamview.cpp)) rendered via a custom QML video surface. The watch screen displays a live 30fps camera preview from the paired smartphone over Bluetooth RFCOMM or local Wi-Fi.

### C. YouTube Music & Network Audio Streaming
* **Upstream**: `asteroid-music` only controls the phone's native media player via AVRCP or plays static local audio files.
* **Matawaa**: Added `music-ytmusic-streaming.patch` providing direct network audio streaming, playlist caching, and playback controls over Wi-Fi directly on the smartwatch.

### D. Native Wearable Telegram Client (`asteroid-telegram`)
* **Upstream**: Not present in AsteroidOS.
* **Matawaa**: Built a dedicated, native Qt/QML Telegram client based on TDLib (`libtdjson`). Features:
  - Custom circular chat bubbles adapted for 1.2"–1.4" AMOLED screens.
  - Quick canned emoji and text replies.
  - Voice memo playback.
  - Aggressive RAM caching capped at under 35 MB resident set size.

### E. Offline Wikipedia & Knowledge Reader (`asteroid-kiwix`)
* **Upstream**: Not present in AsteroidOS.
* **Matawaa**: Created a custom C++/QML front-end for `libzim` allowing offline browsing of full Wikipedia dumps, Wikivoyage travel guides, or medical references stored on the watch's internal eMMC:
  - Custom `ZimImageProvider` for embedded image extraction on low-memory devices.
  - Search indexing optimized for low-power ARM cores.

### F. Wearable Web Engine (`asteroid-browser` & `wpewebkit`)
* **Upstream**: AsteroidOS lacks a web engine due to QtWebEngine's extreme RAM footprint (>500 MB).
* **Matawaa**: Packaged **WPE WebKit** with `cog` and `wpewebkit-qt`, using accelerated OpenGL ES rasterization. Memory usage is constrained within 60–90 MB, allowing the display of captive portal login pages and emergency web lookup.

### G. Asian / CJK Input Method (RIME Wearable Input)
* **Upstream**: AsteroidOS virtual keyboard only supports basic Latin layout alphabets.
* **Matawaa**: Extended the on-screen keyboard engine with `librime` bindings to support predictive Chinese (Pinyin/Zhuyin) and Japanese input directly on circular touch displays.

### H. Modern Storage, Compression & Encryption
* **Upstream Yocto / Android**: Uses Ext4 partitions without compression; Android DM-Crypt.
* **Matawaa**:
  - **Btrfs Transparent Compression**: Enables ZSTD/LZO filesystem compression with `block-group-tree` disabled, allowing Nix store closures to fit within tight 4GB/8GB eMMC flash while maintaining compatibility with legacy vendor Linux 3.10/3.18/4.4 kernels.
  - **`fscrypt` with Adiantum**: Supports hardware-less disk encryption for wearables lacking AES instructions.

### I. Snapdragon Wear 4100 / Fossil Gen 6 Platform Support (`fossil-hoki`)
* **Upstream**: AsteroidOS previously had incomplete or unmerged staging support for Snapdragon Wear 4100 (`sdm429w`).
* **Matawaa**:
  - Integrated custom kernel patches (MMC SDIO fixes, DSI page switching, USB host fallbacks).
  - Packaged the `msm-fb-refresher` continuous splash and framebuffer refresher daemon.
  - Added Wi-Fi firmware shims and force-feedback memless vibration support (`51-ffmemless.ini`).

### J. Tooling & Resilience
* **`resilient-flash`**: Custom interactive flashing utility engineered to recover from USB pin disconnects and pogo-pin bounce commonly encountered when flashing smartwatches on magnetic charging docks.

---

## 4. Summary Table

| Category | Upstream AsteroidOS Component | Matawaa Modification / Addition |
|----------|-------------------------------|----------------------------------|
| **Compositor & Shell** | `asteroid-launcher` | Added rotary crown input (`REL_WHEEL`), gesture tuning, Qt 6 readiness |
| **UI Components** | `qml-asteroid` | Added round display layout helpers, rotary crown list bindings |
| **Camera App** | `asteroid-camera` (shutter button) | Added live MJPEG/RTSP video viewfinder streaming from phone |
| **Music App** | `asteroid-music` (AVRCP remote) | Added direct YouTube Music streaming patch |
| **Games** | `twenty48` | Ported to Qt 6 / modern QML |
| **Messaging** | None | Created `asteroid-telegram` (TDLib-based native circular client) |
| **Offline Docs** | None | Created `asteroid-kiwix` (libzim reader for offline Wikipedia) |
| **Web Browser** | None | Created `asteroid-browser` on low-RAM WPE WebKit |
| **Input Method** | Latin-only virtual keyboard | Added RIME CJK predictive text input support |
| **Hardware Ports** | Legacy Android 5.1/7.1 watches | Added Snapdragon Wear 4100 (`fossil-hoki`), `msm-fb-refresher` |
| **Storage / OS** | OpenEmbedded Yocto images | Btrfs ZSTD compression, `fscrypt` Adiantum, NixOS declarative system |
| **Flashing Tools** | Standard `fastboot` | Created `resilient-flash` with reconnect retry loops |
