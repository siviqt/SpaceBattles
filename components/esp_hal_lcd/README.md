# IDF 6.0.2 LCD HAL compatibility

Badge BSP 2.0.0 requires MIPI abstraction 2.0.0, which reads the ST7701 panel
ID and VCOM OTP. With `CONFIG_MIPI_DSI_ABSTRACTION_USE_VENDORED_ESP_HAL_LCD=y`,
it checks `mipi_dsi_hal_host_gen_read_timed_out()` after both reads. Stock
ESP-IDF 6.0.2 lacks that function and waits indefinitely when a panel does not
answer the read. SpaceBattles enables this option in `sdkconfig.defaults`
and rejects configurations that disable it.

The two vendored files come from Nicolai-Electronics/tanmatsu-launcher commit
[`c7dc85fdcd59b226743b131035041a20dcbe0f95`](https://github.com/Nicolai-Electronics/tanmatsu-launcher/tree/c7dc85fdcd59b226743b131035041a20dcbe0f95/components/esp_hal_lcd):

- `mipi_dsi_hal.c`
- `include/hal/mipi_dsi_hal.h`

They retain the Espressif Apache-2.0 notices. The source adds a 50 ms deadline
for read-command completion and initial receive data, zeroes the result on
timeout, and exposes the timeout flag expected by the MIPI component. MIPI
returns `ESP_ERR_NOT_FOUND` for an unanswered ID or OTP read. The BSP's existing
error propagation remains unmodified; see the
[BSP 2.0.0 migration report](../../BSP-2.0.0-MIGRATION.md) for its limits.

CMake uses the installed IDF's other LCD HAL sources and headers. This override
is restricted to IDF 6.0.2; review it when changing IDF or the MIPI dependency.
The shared SDK and managed components require no manual modifications.
The HAL implementation and provenance are unchanged from the BSP 1.6.2 migration.
