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
| **`virtualkeyboard`**| Custom overlay | Touch keyboard input method engine with RIME Chinese layout support and watch style |
| **`msm-fb-refresher`** | `AsteroidOS/msm-fb-refresher` | Refresh synchronization daemon for Qualcomm MSM display panels |
