# Current release

Release **6** was accepted by the owner as a **pass on 2026-11-02**. It uses
Badge BSP **2.0.0**, MIPI display abstraction **2.0.0**, ESP-IDF **6.0.2** and
PAX **2.2.2**, with automatic support for the second ST7701 panel variant and
the existing bounded-read LCD HAL. The proposed BSP error-propagation and
semaphore-allocation patch remains excluded at the owner's request.

The release includes the accepted gameplay/GUI, SD settings persistence,
reliable LoRa departure, menu rendering, runtime hygiene, MAC unlock and
ECC/AppFS launcher handoff fixes. Radio board/firmware checks, regional
confirmation, encryption and airtime pacing remain in effect. See
[launcher handoff details](LAUNCHER-HANDOFF.md).

All 23 host checks, four radio/color combinations and four fault builds passed.
The installed production image was fully read back and matched its SHA-256;
captured startup confirmed LCD calibration and SD configuration loading. See
the [current migration report](BSP-2.0.0-MIGRATION.md) for evidence and scope.

The accepted image is `build-bsp200/spacebattles.bin`, 1,654,480 bytes:

```text
114b2e0ef2241d956e0da350a87c584ad357f9e71a37124ac087d5faff7828ff
```

The application-repository Git entry `com.github.siviqt.spacebattles/` contains
the same binary with package version `0.4.0`, application revision **8** and
BSP major version **2**. `components/spacebattles/release.h` retains embedded
Release #6. Settings schema and radio protocol versions are unchanged.

After acceptance, obsolete builds, migration baselines/proposals and redundant
device readback were removed. The current source and `build-bsp200/` remain,
including current validation results and the captured startup log.
