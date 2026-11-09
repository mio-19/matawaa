# Patch review — 2026-11-09

This review covers the 43-patch baseline and the follow-up fixes exported after it. It checks upstream recipe parity, Nix packaging, dependency declarations, and reproducible patch application. A successful build is not hardware validation or a claim that the entire downstream tree is ready for nixpkgs submission.

## Upstream references

The baseline pins AsteroidOS's current `meta-asteroid` revision, `c84c0bbd731f9dfa3b04295bac239dd7fa64c722`. Its existing source pins for qml-asteroid, mapplauncherd, bluebinder, and the virtual keyboard match the recipes at that revision. Updating those pins would not address the packaging differences found here.

- [qml-asteroid recipe](https://github.com/AsteroidOS/meta-asteroid/blob/c84c0bbd731f9dfa3b04295bac239dd7fa64c722/recipes-asteroid/qml-asteroid/qml-asteroid_git.bb)
- [Qt launch-cache recipe](https://github.com/AsteroidOS/meta-asteroid/blob/c84c0bbd731f9dfa3b04295bac239dd7fa64c722/recipes-nemomobile/mapplauncherd/mapplauncherd-qt_git.bb)
- [bluebinder recipe](https://github.com/AsteroidOS/meta-asteroid/blob/c84c0bbd731f9dfa3b04295bac239dd7fa64c722/recipes-core/bluebinder/bluebinder.bb)
- [machine-config recipe](https://github.com/AsteroidOS/meta-asteroid/blob/c84c0bbd731f9dfa3b04295bac239dd7fa64c722/recipes-asteroid/asteroid-machine-config/asteroid-machine-config_1.0.bb)

## Findings fixed

| Finding | Correction |
| --- | --- |
| `qml-asteroid` removed its actual launch-cache dependency and replaced `MDeclarativeCache` with inline stub functions. It also installed CMake modules claiming unavailable dependencies were found. | Package upstream `mapplauncherd-qt` at AsteroidOS's exact source pin and build its original qmake projects. Restore upstream source and CMake dependency discovery. Propagate the real dependency to consumers such as alarmclock. Remove the fake cache headers and `FindTimed` replacement. |
| The app builder accepted arbitrary attributes but discarded `postBuild` and `postInstall`. Hackwatch consequently lacked its keyboard helper. | Forward the supported hooks, compose `postFixup`, and reject unsupported arguments. Verify that the resulting hackwatch output contains `keyboard_interface`. |
| The app builder used all of `qml-asteroid` as a native tool dependency. | Package the unchanged upstream desktop-generator shell script separately for the build platform, with declared runtime tools. Keep `qml-asteroid` as the target library dependency. |
| Bluebinder bypassed its Makefile and hard-coded compiler, linker, and dependency flags. | Retain upstream's Makefile; make its pkg-config command configurable and select the cross wrapper explicitly. Let the compiler wrapper supply the Nix build flags. |
| Seven MCE patches and mapplauncherd's Sailjail-query patch duplicated upstream payloads. | Verify byte-for-byte equality and reference the files in the existing fixed-output `meta-asteroid` source. Remove the duplicate files. |
| Keyboard packaging reran `rime_deployer`, passed directory arguments to `--add-schema` as schema names, and ignored deployment/copy failures. | Reuse nixpkgs' already compiled `rime-data`, including its `build` directory. Remove the redundant native deployer and ignored failure paths. |
| `machine.conf` used manual INI interpolation and hard-coded Wi-Fi capability. | Generate the upstream sections and keys with `pkgs.formats.ini`; expose `hasWlan`, constrain gesture fractions to 0–1, and use integer division for the default screen radius. |
| Package metadata misstated qml-asteroid, mapplauncherd, and keyboard licenses. | Match the pinned upstream recipes: LGPL-2.1-only, LGPL-2.1-or-later, and GPL-3.0-only respectively. |
| The ELF audit could falsely report a library missing when `grep -q` caused its upstream `cut` to exit with SIGPIPE under `pipefail`. | Reproduce the failure (exit 141), build a SONAME file once, and search that file directly. The corrected audit passes for the restored cache components. |
| Overlay expressions contained unused dependencies/lambdas, legacy hash spellings, and substitutions that could silently miss their targets. | Remove unused bindings, normalize fixed-output hashes to SRI, use failing substitutions, and format with nixfmt. Check the entire AsteroidOS overlay with deadnix and statix. |
| Qt 6 CMake replacements diverged from upstream ABI and qmake integration. | Compare keepalive, libiodata, and timed against their pinned qmake projects and AsteroidOS recipes. Preserve libiodata and timed qmake feature files; set timed's library SONAME to upstream's major version 0. |

## Scope of alignment

| Baseline patches | Treatment |
| --- | --- |
| 0001–0012: pinning, boot, modules, filesystems, kernel compatibility | Keep NixOS integration. Review watch/module generation separately from boot-sensitive behavior. |
| 0013–0019: Qt, graphics, middleware, launcher infrastructure | Keep the pinned vendor Qt and hardware adaptations. Restore real upstream launch-cache behavior and remove duplicate upstream payloads. |
| 0020–0026: sync, keyboards, apps, browser, Telegram, Wikipedia | Preserve intentional project features: phone input, companion camera control, streaming, and additional apps. Fix the shared packaging boundary rather than deleting those features to reduce the diff. |
| 0027–0029: old-systemd and shared device integration | Preserve kernel compatibility work; rebuilding does not prove old-kernel runtime behavior. |
| 0030–0038: vendor and experimental mainline devices | Preserve hardware source pins, firmware inputs, DTBs/DTS files, and device-specific fixes. No blanket kernel or firmware upgrade without device testing. |
| 0039–0043: installation, desktop, boot ordering | Preserve intentional NixOS deployment and boot integration. Exercise the resulting Fossil Hoki system build. |
| Keyboard availability is folded into patch 0021 and the camera QML resource fix is folded into patch 0022. These changes remain functional diffs, without patch-only whitespace cleanup. |

## Remaining findings and validation limits

1. **Fscrypt configuration is incomplete.** `modules/fscrypt.nix` exposes `user` and `policy`, but neither controls directory provisioning. Enabling the module runs filesystem setup and PAM integration; it does not encrypt the named user's home directory. Do not describe that option as an established encrypted-home implementation. A migration design must handle existing data, login, recovery, and the actual home filesystem before enabling encryption on hardware.
2. **Qt 6 middleware still uses locally maintained CMake projects.** The keepalive source list matches upstream's library and plugin targets; its CMake packaging omits upstream examples/tests, as the AsteroidOS recipe disables tests. `libiodata` and `timed` expose Qt 6 in upstream qmake and AsteroidOS recipes; their CMake replacements remain downstream build-system substitutions. This review restored the qmake feature files, and corrected timed's SONAME to the upstream ABI major. The source/install lists were compared, but no build or third-party consumer check was run for these follow-up changes. Other Qt 6 middleware CMake replacements still need the same package-by-package comparison.
3. **Hardware remains unverified.** Mainline device trees, Aurora's static vendor boot data, graphics pacing, Bluetooth pairing, suspend/wake, audio routing, and the actual camera/keyboard UX need on-device testing. This review does not deploy or flash a watch.
4. **Cross QML discovery warns about modules.** The full cross build cannot always run target QML discovery tools. Those warnings are not proof of missing runtime modules; packaging and the system profile must provide them, and on-device imports still need checking.

## Validation

- Applied all 43 baseline patches to a fresh checkout of the locked Mobile NixOS revision; its tree matched the working baseline exactly.
- Cross-built qml-asteroid with the real launch cache, bluebinder, and the virtual keyboard for Fossil Hoki.
- Cross-built camera and hackwatch; checked the installed keyboard helper.
- Ran nixfmt, deadnix, and statix over the AsteroidOS overlay and checked the touched watch modules.
- Applied the four review follow-ups after folding the keyboard and camera fixes into their owning patches. All 47 patches apply without three-way fallback, and the resulting tree exactly matches the committed working checkout.
- Built the final Fossil Hoki system: `/nix/store/x30cqpmnjj0a5cym5x1b14kz6cw7f8av-nixos-system-nixos-26.11pre-git`.
- Evaluated the complete system derivations for `oppo-beluga`, `google-aurora`, and `fossil-hoki-mainline`.
- Audited the launch-cache library, Qt booster, and Asteroid app library (7 ELF paths in a 2,014-ELF runtime closure): no missing NEEDED entries or unresolved symbols. Confirmed the launch-cache package does not reference the build machine's Qt runtime.
- Generated `machine.conf` with `borderGestureWidth = 0.15` and `hasWlan = false`; checked the upstream-compatible sections, boolean values, and fraction. Confirmed that `borderGestureWidth = 1.5` fails option validation.
- Ran `bash -n` on the corrected ELF audit script and reproduced the original SIGPIPE false positive with a large SONAME fixture.

Follow-up changes are exported as patches 0044–0047; keyboard and camera fixes remain in patches 0021 and 0022. The root flake's unused module arguments and the ELF audit fix are direct repository edits. The feature fixes are retained in their owning patches. No review changes were deployed or published.
