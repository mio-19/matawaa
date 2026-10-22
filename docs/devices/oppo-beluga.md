# OPPO Watch 46mm (`oppo-beluga` / Model OW19W8) Device Notes

The **OPPO Watch 46mm** (Model **OW19W8**, codename `beluga` / `oppo-beluga`) is a premier target smartwatch platform for NixOS for Smartwatches. It features Qualcomm Snapdragon Wear 3100 silicon, a 1.91″ 3D dual-curved flexible AMOLED display (402×476 curved squircle), 1 GB RAM, and VOOC Flash Charging.

---

## Hardware Specifications

| Component | Specification | Notes |
| :--- | :--- | :--- |
| **Model** | OW19W8 (Global / Wi-Fi & Bluetooth) | Also known as OPPO Watch 46mm |
| **SoC** | Qualcomm Snapdragon Wear 3100 (SDA429W) | 4× ARM Cortex-A7 @ 1.2 GHz, Adreno 304 GPU |
| **Co-Processor** | Ambiq Micro Apollo 3 Wireless MCU | Ultra-low power co-processor for sensor hub / ambient mode |
| **Memory** | 1 GB LPDDR3 | Shared system RAM |
| **Storage** | 8 GB eMMC 4.51 | High-speed on-board flash storage |
| **Display** | 1.91″ 3D Flexible Dual-Curved AMOLED (402×476, ~326 ppi) | 100% DCI-P3 color gamut, curved squircle viewport |
| **Touch** | Capacitive multi-touch | 3D curved edge touch controller |
| **Controls** | 2 Hardware Push-Buttons | Upper navigation/app button + Lower multi-function/power button |
| **Haptics** | Linear Resonant Actuator (LRA) | Force-feedback motor via `ngfd` |
| **Wireless** | Wi-Fi 802.11 b/g/n (2.4 GHz) + Bluetooth 4.2 LE | BlueZ dual-mode stack |
| **Sensors** | Optical heart rate (PPG), 3-axis accelerometer, gyroscope, geomagnetic, barometric, ambient light | Sensor hub integration |
| **Battery & Charging** | 430 mAh with Watch VOOC Flash Charging | Pogo-pin charging dock (5V / 1.5A) |

---

## Bootloader & Fastboot Access

1. **Enter Fastboot via ADB**:
   ```bash
   adb reboot bootloader
   ```
2. **Hardware Key Combination**:
   * Power off the watch completely.
   * Hold down both the **Upper Button** and **Lower Button** simultaneously until the bootloader / fastboot menu appears.
3. **Verify Host Connection**:
   ```bash
   fastboot devices
   ```

---

## Flashing NixOS

```bash
# 1. Build the system image on host:
nix-build examples/asteroid --argstr device oppo-beluga -A outputs.default

# 2. Flash kernel and initramfs:
fastboot flash boot result/boot.img

# 3. Flash root filesystem to userdata partition:
fastboot flash userdata result/system.img

# 4. Wipe cache and reboot:
fastboot format cache
fastboot reboot
```

---

## Squircle Display Geometry

The OPPO Watch features a unique 402×476 dual-curved rectangular display with rounded corners ("squircle"). In NixOS for Smartwatches:
* `mobile.hardware.screen.shape = "squircle"`
* Compositor and Wayland clients center UI content within safe rectangular margins while maintaining full bleed background rendering.
