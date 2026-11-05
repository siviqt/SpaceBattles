# Override only the IDF 6.0.2 MIPI HAL; reuse its remaining sources and headers.
if(NOT IDF_VERSION_MAJOR EQUAL 6 OR NOT IDF_VERSION_MINOR EQUAL 0 OR NOT IDF_VERSION_PATCH EQUAL 2)
    message(FATAL_ERROR "Review the SpaceBattles LCD HAL override before changing ESP-IDF 6.0.2")
endif()
set(idf_lcd "${IDF_PATH}/components/esp_hal_lcd")
idf_component_register(
    SRCS "mipi_dsi_hal.c" "${idf_lcd}/lcd_hal.c"
         "${idf_lcd}/esp32p4/lcd_periph.c" "${idf_lcd}/esp32p4/mipi_dsi_periph.c"
    INCLUDE_DIRS "include" "${idf_lcd}/include" "${idf_lcd}/esp32p4/include"
    PRIV_REQUIRES esp_hal_i2s esp_timer
    REQUIRES soc hal
)
