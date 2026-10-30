# AsteroidOS Overlay & App Packaging Guidelines

This overlay provides the **AsteroidOS Userland and Wearable Desktop Stack** for NixOS for Smartwatches, including the Wayland compositor (`asteroid-launcher`), toolkit libraries (`qml-asteroid`, `mlite`, `amber-mpris`), and touch-optimized smartwatch applications.

---

## Packaging Guidelines

### 1. No Vendored Code Duplication
- **Rule**: Do not vendor or duplicate complete third-party or upstream application source trees inside the repository.
- **Pattern**: Always fetch the genuine upstream source repository using `fetchFromGitHub` or `fetchGit`, and apply minimal, clean `.patch` files where needed for NixOS or Qt 6 compatibility.
- **Rationale**: Prevents unvetted, unmaintained, or hallucinated code dumps from entering the repository, and ensures transparent diff tracking against upstream releases.

### 2. Qt 6 QML Module URI Identifier Rule
In Qt 6 CMake macros (`qt6_add_qml_module`), URI components must follow valid QML identifier naming rules:
- **Requirement**: The module URI **must start with an alphabetic letter** (e.g. `Twenty48`, not `2048`).
- **Example**:
  ```cmake
  # In src/CMakeLists.txt:
  qt6_add_qml_module(${CMAKE_PROJECT_NAME}
      URI Twenty48
      VERSION 1.0
      RESOURCE_PREFIX "/"
      NO_PLUGIN
      QML_FILES
          main.qml
          Game.qml
  )
  ```
- **In C++ entrypoint (`main.cpp`)**:
  ```cpp
  view->setSource(QUrl(QStringLiteral("qrc:/Twenty48/main.qml")));
  ```

### 3. Using `mkAsteroidApp`
The helper function `overlay/asteroidos/lib/mk-asteroid-app.nix` provides standardized derivation scaffolding for AsteroidOS applications:
- Handles cross-compilation tool paths for `Qt6QmlTools`, `Qt6QuickTools`, `Qt6ShaderToolsTools`, and `Qt6LinguistTools`.
- Injects standard Extra CMake Modules (`ECM`) and `Asteroid6CMakeSettings`.
- Wraps Qt binaries using `wrapQtAppsHook`.

Example definition:
```nix
twenty48 = mkAsteroidApp {
  name = "2048";
  pname = "asteroid-2048";
  owner = "MagneFire";
  repo = "asteroid-2048";
  desc = "Sliding-tile 2048 puzzle game for AsteroidOS smartwatches";
  rev = "99e7f00228c269069b41c4a27a0a60d2ed2ac7cf";
  sha256 = "16xzqx0ry4y8hx6gqigafqx6izjahjlz5jc5s12fg0rjk5ylxjx0";
  patches = [
    ./twenty48-qt6.patch
  ];
};
```

---

## Core Desktop Components

| Component | Upstream / Reference | Role |
| :--- | :--- | :--- |
| **`asteroid-launcher`** | `AsteroidOS/asteroid-launcher` | Wayland compositor, watchface host, quick settings, and notifications shell |
| **`qml-asteroid`** | `AsteroidOS/qml-asteroid` | Wearable UI controls (swipes, icons, pagers, lists) |
| **`asteroid-btsyncd`** | `AsteroidOS/asteroid-btsyncd` | BLE sync daemon communicating with AsteroidOS Sync companion app |
| **`amber-mpris`** | `sailfishos/amber-mpris` | D-Bus MPRIS remote media control bindings |
| **`mlite`** | `sailfishos/mlite` | Lightweight dconf / GSettings integration for Qt |
| **`timed`** | `sailfishos/timed` | Alarm/clock daemon with the `voland` client library, backing Nemo.Alarms |
| **`nemo-qml-plugin-alarms`** | `sailfishos/nemo-qml-plugin-alarms` | `Nemo.Alarms` QML bindings used by the clock and alarm presenters |
| **`nemo-qml-plugin-notifications`** | `sailfishos/nemo-qml-plugin-notifications` | `Nemo.Notifications` QML bindings for toast notifications |
| **`virtualkeyboard`**| Custom overlay | Touch keyboard input method engine with RIME Chinese layout support and watch style |
| **`msm-fb-refresher`** | `AsteroidOS/msm-fb-refresher` | Refresh synchronization daemon for Qualcomm MSM display panels |

---

## AppBridge Security Model (phone camera remote)

The watch talks to the phone through the `asteroid-btsyncd` AppBridge GATT service
(`0000A071-...`). The phone camera is a remote shutter/control only: there is **no
network path** (no HTTP/MJPEG/RTSP, no sockets, no IPs or ports exchanged) and **no live
viewfinder**. The phone app has no `INTERNET` permission and never tells the watch to
connect anywhere.

### Threat model
- Untrusted: any BLE peer that manages to write the RX characteristic, and any local
  process or user other than the watch session user.
- Trusted: the bonded phone, after LE encryption with authentication
  (`encrypt-authenticated-*` characteristic flags), and `root` / `ceres` on the watch.
- Goal: a malicious or buggy peer can at most trigger the fixed camera remote actions
  below; it cannot make the watch open connections, parse variable payloads or reach
  other D-Bus services through btsyncd.

### Frame format
`[0xA0][appIdLen:1][appId][actionLen:1][action][payload]`, at most 512 bytes in total.
App ids and actions are lowercase `[a-z0-9_.]` tokens of at most 64 bytes. Wire alias
`cam` maps to `org.asteroidos.camera` and `spo2` to `org.asteroidos.spo2`; every other
app id is dropped. Camera frames carry an empty payload in both directions; spo2
payloads are capped at 256 bytes. Payload contents are never logged.

### Allowlists
| Direction | Camera actions |
|---|---|
| watch -> phone | `capture`, `flip`, `zoom_in`, `zoom_out`, `torch`, `mode_photo`, `mode_video`, `status_query` |
| phone -> watch | `ready`, `paused`, `photo_captured`, `video_started`, `video_stopped` |

Anything else is dropped with a warning on receive, and rejected by the D-Bus
`sendMessage`/`sendBytes` methods on send. `camera-shutter` and the `RemoteCameraBridge`
class of `asteroid-camera` apply the same watch -> phone allowlist before calling D-Bus.

### D-Bus policy
`org.asteroidos.btsyncd.conf` is deny-by-default. Only `root` and `ceres` (the
unprivileged session user running `asteroid-btsyncd` and the apps) may own, send to or
receive from `org.asteroidos.btsyncd`. `asteroid-btsyncd` exits if it cannot register
that name.
