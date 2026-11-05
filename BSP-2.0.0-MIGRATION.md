# BSP 2.0.0 migration

Implemented 2026-11-01. SpaceBattles remains release 6. Settings paths/schema,
radio protocol, gameplay and artwork are unchanged. The owner approved the
migration while explicitly excluding the proposed BSP hardening patch.
The owner accepted this firmware as a **pass on 2026-11-02**.

## Changes

- Pin Badge BSP 2.0.0. The component manager regenerated `dependencies.lock`
  and selected MIPI abstraction 2.0.0. Every other resolved dependency version
  remains unchanged, including IDF 6.0.2, PAX 2.2.2, ES8156 0.1.0, LoRa 0.6.0,
  Hosted 2.12.3~1, Wi-Fi Remote 1.4.2 and coprocessor 0.8.0. The lockfile also
  reorders one existing BSP dependency without changing its version.
- Enable `CONFIG_MIPI_DSI_ABSTRACTION_USE_VENDORED_ESP_HAL_LCD=y` in
  `sdkconfig.defaults`. MIPI 2.0.0 defaults this option off; enabling it makes
  the driver check the HAL timeout flag after both panel-ID and VCOM OTP reads.
  Application CMake rejects a configuration that disables it, after IDF's
  early dependency expansion has completed.
- Retain the pinned local IDF 6.0.2 LCD HAL implementation without source
  changes. Its bounded reads now also protect the new three-byte panel-ID read.
  See [HAL provenance and configuration](components/esp_hal_lcd/README.md).
- Use MIPI's automatic initialization-sequence selection for the second
  ST7701 panel variant (`42 00 01`). Resolution, rotation and supported RGB565/
  RGB888 formats remain the same. No game or renderer rewrite was needed.
- Retain the application's display callback, one-second completion timeout and
  framebuffer-retention rules. BSP 2.0.0 still supplies a no-op weak Tanmatsu
  display wait. BSP SD ownership, worker deadlines, read-only calibration
  lookup, ECC launcher handoff and AppFS image handling remain intact.

## Package verification

The component manager fetched the published registry packages rather than using
local path overrides. Their content matches the reviewed SDK snapshots, apart
from registry manifest metadata and excluded upload-workflow files. All files
listed in each package's published `CHECKSUMS.json` were verified after the build:
104 BSP files and 14 MIPI files, with no modifications.

Published source revisions:

- [BSP 2.0.0](https://github.com/badgeteam/esp32-component-badge-bsp/tree/8e9e033f74fd5b0b62323f291687c56111e049b3),
  component hash `81b73f9536a1e4beb03dbc743a29214b39fdf75d094e654b875ea0b8e0fb6f32`.
- [MIPI 2.0.0](https://github.com/Nicolai-Electronics/esp32-component-mipi-dsi-abstraction/tree/8a2d9f6377a7150911a0f2a1ec3212f0052a67bc),
  component hash `4347e6e2be462590fa90db7846bea53016ef98035b1ab8e1184062d95ef134d1`.

No BSP patch, managed-component source edit or shared SDK source change was made.

## Automated verification

All 23 host checks passed: every `tools/test-*.py` script and
`tools/investigate-lora-countdown.py`.

The new `test-display-driver.py` compiles the actual resolved MIPI driver and
unmodified Tanmatsu BSP display implementation against IDF/hardware mocks. Its
26 cases cover both pixel formats, both panel initialization sequences,
unknown-ID and failed-ID fallback, ID/OTP timeouts, panel creation/init failure,
callback/TE failure, and present/missing/unavailable NVS calibration. A test-only
linker wrapper records the driver's return value without changing BSP behavior.
`test-lcd-hal.py` now checks both one-byte OTP and three-byte ID reads, buffer
guards, both timeout paths and recovery. Existing platform and lifecycle checks
continue to cover presentation completion, NVS fallback and failure cleanup.

Firmware verification passed:

| Radio | Pixel format | Image bytes |
| --- | --- | ---: |
| ON | RGB565 | 1,654,480 |
| OFF | RGB565 | 1,625,184 |
| ON | RGB888 | 1,654,496 |
| OFF | RGB888 | 1,625,200 |

I2C, display, audio and transfer fault builds also passed. Production was built
in a fresh `build-bsp200/` directory with a fresh configuration. The first
variant was a clean compilation using a copy of the pre-upgrade `sdkconfig`;
the remaining variants reused `build-bsp200-variants/`. After validation, that
directory was restored to radio ON, RGB565, fault none. Production remained in
its separate directory throughout.

The generated fresh and migrated configurations have identical `CONFIG_*`
values, including enabled MIPI timeout detection. After acceptance, the root
`sdkconfig` was synchronized with the accepted production configuration.
A separate configuration with timeout detection disabled was rejected before
compilation, as intended.

Build the production configuration with an activated ESP-IDF 6.0.2
environment and its required Python packages:

```sh
SB_BUILD_DIR=build-bsp200 SB_SDKCONFIG=build-bsp200/sdkconfig bash tools/build.sh
```

## Production artifact and comparison

Application image: `build-bsp200/spacebattles.bin`, 1,654,480 bytes, SHA-256:

```text
114b2e0ef2241d956e0da350a87c584ad357f9e71a37124ac087d5faff7828ff
```

Compared with the BSP 1.6.2 production image, the binary grows by
1,472 bytes. Link-map DIRAM use grows by 300 bytes: 4 bytes of text, 56 bytes
of BSS and 240 bytes of data. These are linked sizes, not runtime heap readings.

After owner acceptance, the superseded builds, migration baseline archive and
temporary variant/guard build directories were removed. Only `build-bsp200/`
is retained. Current host/build result JSON, package integrity and size comparison
remain under `build-bsp200/validation/`.

The application-repository Git entry `com.github.siviqt.spacebattles/` was updated
with the identical accepted binary, application revision 8 and BSP major 2.
Package version `0.4.0` and embedded Release #6 remain unchanged.

## Hardware validation

Installed the production image on the reachable Tanmatsu through BadgeLink as
AppFS slug `spacebattles`, title `SpaceBattles`, version 6. The unit previously
had only `nokia5110`; its metadata and device CRC32 were checked before and
after installation and remain identical. No bootloader, partition table,
launcher or radio firmware was installed.

A complete device readback matched the production SHA-256 above; the redundant
readback file was removed after acceptance. The application was started from
the launcher, and USB serial was reconnected after normal application-start
re-enumeration.
The captured `build-bsp200/hardware-startup.log` identifies release 6 and ELF
prefix `d16b9cb07`, and records:

- Panel ID `FF FF FF`, selecting the driver's original/default initialization
  sequence. The second panel variant was exercised by host tests, not observed
  on this device.
- VCOM OTP `0x40` and application of the existing NVS calibration `0x46`.
- SD initialization and successful loading of the existing SD configuration.
- No panic, startup-failure message or display-completion timeout in the capture.

The other connected debug port did not answer the documented launcher
handshakes; no application was installed on that unit. The AppFS installation and
readback hashes remain recorded in `build-bsp200/validation/device-installation.json`.

The owner subsequently accepted the current firmware as a pass on 2026-11-02.
No additional individual hardware-test results were enumerated. The automated
and captured startup evidence above remains distinct from that owner acceptance.
Only production RGB565 was installed during the recorded verification; RGB888
and fault variants were built only.

## Unmodified upstream limits

As requested, the BSP's error-propagation and semaphore-allocation improvement
was excluded. Its panel initializer still discards `st7701_initialize()`'s return
value, and its display semaphore allocations remain unchecked. The new test
reproduces the released behavior: ID/OTP timeout reaches a later invalid-panel
error, while an injected panel-init failure with an allocated panel can be
reported as successful by the BSP. Passing this characterization test does not
mean those upstream issues have been fixed.
