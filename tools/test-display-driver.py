#!/usr/bin/env python3
"""Exercise the resolved ST7701 driver and unmodified Tanmatsu BSP display code.

Only IDF/hardware calls are mocked. The test-only linker wrapper records the
driver result without changing the BSP's existing error handling.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
bsp = root / 'managed_components/badgeteam__badge-bsp'
mipi = root / 'managed_components/nicolaielectronics__mipi_dsi_abstraction'

mock = r'''
#pragma once
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CONFIG_MIPI_DSI_ABSTRACTION_USE_VENDORED_ESP_HAL_LCD 1
#define IRAM_ATTR
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_ARG 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_ERR_NOT_FOUND 3
#define LCD_COLOR_FMT_RGB565 16
#define LCD_COLOR_FMT_RGB888 24
#define MIPI_DSI_DPI_CLK_SRC_DEFAULT 0
#define LCD_RGB_ELEMENT_ORDER_RGB 0
#define LCD_CMD_RDDID 0x04
#define LCD_CMD_NORON 0x13
#define LCD_CMD_SLPOUT 0x11
#define LCD_CMD_DISPON 0x29
#define LCD_CMD_MADCTL 0x36
#define LCD_CMD_COLMOD 0x3a
#include "tanmatsu_hardware.h"
#define GPIO_MODE_INPUT 0
#define GPIO_INTR_POSEDGE 1
#define BIT64(n) (UINT64_C(1) << (n))
#define NVS_READONLY 0
#define pdMS_TO_TICKS(n) (n)
#define ESP_RETURN_ON_ERROR(call,tag,...) do { int e=(call); test_log(tag,__VA_ARGS__); if(e!=ESP_OK) return e; } while(0)
#define ESP_RETURN_ON_FALSE(value,error,tag,...) do { test_log(tag,__VA_ARGS__); if(!(value)) return error; } while(0)
#define ESP_LOGI(...) test_log(__VA_ARGS__)
#define ESP_LOGW(...) test_log(__VA_ARGS__)
#define ESP_LOGE(...) test_log(__VA_ARGS__)
typedef int esp_err_t;
typedef int gpio_num_t;
typedef int lcd_color_format_t;
typedef void *esp_lcd_panel_handle_t;
typedef void *esp_lcd_panel_io_handle_t;
typedef void *esp_lcd_dsi_bus_handle_t;
typedef void *esp_ldo_channel_handle_t;
typedef void *tanmatsu_coprocessor_handle_t;
typedef void *SemaphoreHandle_t;
typedef unsigned nvs_handle_t;
typedef struct { int bus_id,num_data_lanes,lane_bit_rate_mbps; } esp_lcd_dsi_bus_config_t;
typedef struct { int virtual_channel,lcd_cmd_bits,lcd_param_bits; } esp_lcd_dbi_io_config_t;
typedef struct {
    int virtual_channel,dpi_clk_src,dpi_clock_freq_mhz,in_color_format;
    size_t num_fbs;
    struct { int h_size,v_size,hsync_back_porch,hsync_pulse_width,hsync_front_porch;
             int vsync_back_porch,vsync_pulse_width,vsync_front_porch; } video_timing;
} esp_lcd_dpi_panel_config_t;
typedef struct { int cmd; const void *data; size_t data_bytes; unsigned delay_ms; } st7701_lcd_init_cmd_t;
typedef struct {
    const st7701_lcd_init_cmd_t *init_cmds;
    size_t init_cmds_size;
    struct { esp_lcd_dsi_bus_handle_t dsi_bus; const esp_lcd_dpi_panel_config_t *dpi_config; } mipi_config;
    struct { bool use_mipi_interface; } flags;
} st7701_vendor_config_t;
typedef struct { int reset_gpio_num,rgb_ele_order,bits_per_pixel; const void *vendor_config; } esp_lcd_panel_dev_config_t;
typedef struct { int chan_id,voltage_mv; } esp_ldo_channel_config_t;
typedef struct { uint64_t pin_bit_mask; int mode,pull_up_en,pull_down_en,intr_type; } gpio_config_t;
typedef struct { int unused; } esp_lcd_dpi_panel_event_data_t;
typedef struct { bool (*on_color_trans_done)(esp_lcd_panel_handle_t,esp_lcd_dpi_panel_event_data_t *,void *); } esp_lcd_dpi_panel_event_callbacks_t;
void test_log(const char *,const char *,...);
const char *esp_err_to_name(int);
int esp_lcd_new_dsi_bus(const esp_lcd_dsi_bus_config_t *,void **);
int esp_lcd_new_panel_io_dbi(void *,const esp_lcd_dbi_io_config_t *,void **);
int esp_lcd_panel_io_rx_param(void *,int,void *,size_t);
int esp_lcd_panel_io_tx_param(void *,int,const void *,size_t);
int esp_lcd_new_panel_st7701(void *,const esp_lcd_panel_dev_config_t *,void **);
int esp_lcd_dpi_panel_enable_dma2d(void *);
int esp_lcd_dpi_panel_disable_dma2d(void *);
int esp_lcd_panel_reset(void *);
int esp_lcd_panel_init(void *);
int esp_lcd_panel_del(void *);
int esp_lcd_panel_draw_bitmap(void *,int,int,int,int,const void *);
int esp_lcd_dpi_panel_register_event_callbacks(void *,const esp_lcd_dpi_panel_event_callbacks_t *,void *);
bool mipi_dsi_hal_host_gen_read_timed_out(void);
int esp_ldo_acquire_channel(const esp_ldo_channel_config_t *,void **);
int gpio_config(const gpio_config_t *);
int gpio_isr_handler_add(int,void (*)(void *),void *);
SemaphoreHandle_t xSemaphoreCreateBinary(void);
int xSemaphoreGive(void *);
int xSemaphoreGiveFromISR(void *,void *);
int xSemaphoreTake(void *,unsigned);
void vTaskDelay(unsigned);
int bsp_tanmatsu_coprocessor_get_handle(void **);
int tanmatsu_coprocessor_get_display_backlight(void *,uint8_t *);
int tanmatsu_coprocessor_set_display_backlight(void *,uint8_t);
int nvs_open(const char *,int,unsigned *);
int nvs_get_u8(unsigned,const char *,uint8_t *);
void nvs_close(unsigned);
'''

harness = r'''
#include "bsp/display.h"
#include "dsi_panel_nicolaielectronics_st7701.h"
esp_err_t bsp_display_initialize(const bsp_display_configuration_t *);
esp_err_t __real_st7701_initialize(const st7701_configuration_t *);
enum { ORIGINAL, SECOND, UNKNOWN_ID, ID_ERROR, ID_TIMEOUT, OTP_TIMEOUT,
       PANEL_ERROR, INIT_ERROR, NVS_MISSING, NVS_UNAVAILABLE, OTP_ERROR,
       TE_ERROR, CALLBACK_ERROR, CASE_COUNT };
static int scenario,bits,driver_result,reads,resets,creates,inits,deletes,semaphores;
static int nvs_opens,nvs_reads,nvs_closes,page,hardware_vcom=-1,porch=-1,color_mode=-1;
static bool timed_out;
static const st7701_lcd_init_cmd_t *sequence;
static size_t sequence_size;
static const uint8_t original_id[3]={0x77,0x01,0x00},second_id[3]={0x42,0x00,0x01};

esp_err_t __wrap_st7701_initialize(const st7701_configuration_t *config) {
    driver_result=__real_st7701_initialize(config);
    return driver_result;
}
void test_log(const char *tag,const char *format,...) { (void)tag;(void)format; }
const char *esp_err_to_name(int e) { (void)e;return "mock"; }
int esp_lcd_new_dsi_bus(const esp_lcd_dsi_bus_config_t *c,void **out) {
    assert(c->bus_id==0 && c->num_data_lanes==2 && c->lane_bit_rate_mbps==500);
    *out=(void*)1;return ESP_OK;
}
int esp_lcd_new_panel_io_dbi(void *bus,const esp_lcd_dbi_io_config_t *c,void **out) {
    assert(bus==(void*)1 && c->virtual_channel==0 && c->lcd_cmd_bits==8 && c->lcd_param_bits==8);
    *out=(void*)2;return ESP_OK;
}
int esp_lcd_panel_io_rx_param(void *io,int command,void *out,size_t n) {
    assert(io==(void*)2);++reads;timed_out=false;
    if(command==LCD_CMD_RDDID) {
        assert(reads==1 && n==3 && !resets && !creates);
        if(scenario==ID_ERROR) return ESP_FAIL;
        timed_out=scenario==ID_TIMEOUT;
        const uint8_t unknown[3]={0xfe,0xdc,0xba};
        memcpy(out,scenario==SECOND ? second_id : scenario==UNKNOWN_ID ? unknown : original_id,3);
    } else {
        assert(command==0xb1 && n==1 && reads==2 && resets==1 && !inits && page==0x11);
        if(scenario==OTP_ERROR) return ESP_FAIL;
        timed_out=scenario==OTP_TIMEOUT;*(uint8_t*)out=0x40;
    }
    if(timed_out) memset(out,0,n);
    return ESP_OK;
}
bool mipi_dsi_hal_host_gen_read_timed_out(void) { return timed_out; }
int esp_lcd_panel_io_tx_param(void *io,int command,const void *data,size_t n) {
    assert(io==(void*)2);const uint8_t *p=data;
    if(command==0xff) { assert(n==5);page=p[4]; }
    if(command==0xb1 && page==0x11) { assert(n==1);hardware_vcom=p[0]; }
    if(command==0xc1 && page==0x10) { assert(n==2);porch=p[0]; }
    if(command==LCD_CMD_COLMOD) { assert(n==1);color_mode=p[0]; }
    return ESP_OK;
}
int esp_lcd_new_panel_st7701(void *io,const esp_lcd_panel_dev_config_t *c,void **out) {
    assert(io==(void*)2 && c->reset_gpio_num==BSP_LCD_RESET_PIN && c->bits_per_pixel==bits);
    const st7701_vendor_config_t *v=c->vendor_config;
    const esp_lcd_dpi_panel_config_t *dpi=v->mipi_config.dpi_config;
    assert(v->flags.use_mipi_interface && v->mipi_config.dsi_bus==(void*)1);
    assert(dpi->num_fbs==1 && dpi->in_color_format==bits);
    assert(dpi->video_timing.h_size==480 && dpi->video_timing.v_size==800);
    assert(dpi->dpi_clock_freq_mhz==30);
    if(scenario==PANEL_ERROR) return ESP_FAIL;
    sequence=v->init_cmds;sequence_size=v->init_cmds_size;
    assert(sequence && sequence_size>30);
    *out=(void*)3;++creates;return ESP_OK;
}
int esp_lcd_dpi_panel_enable_dma2d(void *panel) { assert(panel==(void*)3);return ESP_OK; }
int esp_lcd_dpi_panel_disable_dma2d(void *panel) { assert(panel==(void*)3);return ESP_OK; }
int esp_lcd_panel_reset(void *panel) { assert(panel==(void*)3);++resets;return ESP_OK; }
int esp_lcd_panel_init(void *panel) {
    assert(panel==(void*)3 && resets==1 && reads==2);++inits;
    if(scenario==INIT_ERROR) return ESP_FAIL;
    for(size_t i=0;i<sequence_size;i++)
        assert(esp_lcd_panel_io_tx_param((void*)2,sequence[i].cmd,sequence[i].data,sequence[i].data_bytes)==ESP_OK);
    return ESP_OK;
}
int esp_lcd_panel_del(void *panel) { assert(panel==(void*)3);++deletes;return ESP_OK; }
int esp_lcd_panel_draw_bitmap(void *p,int x,int y,int w,int h,const void *b) {
    (void)p;(void)x;(void)y;(void)w;(void)h;(void)b;return ESP_OK;
}
int esp_lcd_dpi_panel_register_event_callbacks(void *panel,const esp_lcd_dpi_panel_event_callbacks_t *c,void *ctx) {
    assert(c && c->on_color_trans_done && !ctx);
    if(!panel) return ESP_ERR_INVALID_ARG;
    assert(panel==(void*)3);
    return scenario==CALLBACK_ERROR ? ESP_FAIL : ESP_OK;
}
int esp_ldo_acquire_channel(const esp_ldo_channel_config_t *c,void **out) {
    assert(c->chan_id==3 && c->voltage_mv==2500);*out=(void*)4;return ESP_OK;
}
int gpio_config(const gpio_config_t *c) {
    assert(c->pin_bit_mask==BIT64(BSP_LCD_TE_PIN));return scenario==TE_ERROR ? ESP_FAIL : ESP_OK;
}
int gpio_isr_handler_add(int pin,void (*callback)(void *),void *ctx) {
    assert(pin==BSP_LCD_TE_PIN && callback && !ctx);return ESP_OK;
}
SemaphoreHandle_t xSemaphoreCreateBinary(void) { return (void*)(uintptr_t)(10+ ++semaphores); }
int xSemaphoreGive(void *s) { assert(s);return 1; }
int xSemaphoreGiveFromISR(void *s,void *wake) { (void)wake;return xSemaphoreGive(s); }
int xSemaphoreTake(void *s,unsigned ticks) { assert(s && ticks==1000);return 1; }
void vTaskDelay(unsigned ticks) { assert(ticks==100); }
int bsp_tanmatsu_coprocessor_get_handle(void **out) { *out=(void*)5;return ESP_OK; }
int tanmatsu_coprocessor_get_display_backlight(void *h,uint8_t *out) { assert(h==(void*)5);*out=255;return ESP_OK; }
int tanmatsu_coprocessor_set_display_backlight(void *h,uint8_t value) { assert(h==(void*)5);(void)value;return ESP_OK; }
int nvs_open(const char *name,int mode,unsigned *out) {
    assert(!strcmp(name,"system") && mode==NVS_READONLY);++nvs_opens;
    if(scenario==NVS_UNAVAILABLE) return ESP_FAIL;
    *out=1;return ESP_OK;
}
int nvs_get_u8(unsigned handle,const char *key,uint8_t *out) {
    assert(handle==1 && !strcmp(key,"lcd_vcom"));++nvs_reads;
    if(scenario==NVS_MISSING) return ESP_ERR_NOT_FOUND;
    *out=0x46;return ESP_OK;
}
void nvs_close(unsigned handle) { assert(handle==1);++nvs_closes; }

int main(int argc,char **argv) {
    assert(argc==3);scenario=atoi(argv[1]);bits=atoi(argv[2]);
    assert(scenario>=0 && scenario<CASE_COUNT && (bits==16 || bits==24));
    uint8_t id[3],otp;
    assert(st7701_get_id(id)==ESP_ERR_INVALID_STATE);
    assert(st7701_get_id(NULL)==ESP_ERR_INVALID_ARG);
    const bsp_display_configuration_t config={.requested_color_format=bits==24 ? BSP_DISPLAY_COLOR_FORMAT_24_888RGB : BSP_DISPLAY_COLOR_FORMAT_16_565RGB,.num_fbs=1};
    int result=bsp_display_initialize(&config);
    bool early=scenario==ID_TIMEOUT || scenario==OTP_TIMEOUT || scenario==PANEL_ERROR;
    assert(driver_result==(scenario==ID_TIMEOUT || scenario==OTP_TIMEOUT ? ESP_ERR_NOT_FOUND :
                           scenario==PANEL_ERROR || scenario==INIT_ERROR ? ESP_FAIL : ESP_OK));
    // Characterize the released BSP, including its unmodified error masking.
    assert(result==(early ? ESP_ERR_INVALID_ARG : scenario==TE_ERROR || scenario==CALLBACK_ERROR ? ESP_FAIL : ESP_OK));
    assert(st7701_is_display_variant_2()==(scenario==SECOND));
    assert(st7701_get_id(id)==(scenario==ID_ERROR || scenario==ID_TIMEOUT ? ESP_ERR_INVALID_STATE : ESP_OK));
    if(scenario==SECOND) assert(!memcmp(id,second_id,3));
    assert(deletes==(scenario==OTP_TIMEOUT));
    assert(st7701_get_vcom_otp(&otp)==(early || scenario==OTP_ERROR ? ESP_ERR_INVALID_STATE : ESP_OK));
    if(!early && scenario!=OTP_ERROR) assert(otp==0x40);
    void *panel=NULL;
    assert(bsp_display_get_panel(&panel)==(result==ESP_OK ? ESP_OK : ESP_FAIL));
    if(result==ESP_OK) {
        size_t w=0,h=0;bsp_display_color_format_t format;bsp_display_endianness_t endian;
        assert(panel==(void*)3 && bsp_display_get_parameters(&w,&h,&format,&endian)==ESP_OK);
        assert(w==480 && h==800 && endian==BSP_DISPLAY_ENDIAN_LITTLE);
        assert(format==config.requested_color_format && bsp_display_get_default_rotation()==BSP_DISPLAY_ROTATION_270);
    }
    if(!early && scenario!=INIT_ERROR) {
        assert(porch==(scenario==SECOND ? 0x0c : 0x10));
        assert(color_mode==(bits==24 ? 0x77 : 0x55));
    }
    bool calibrated=!early && scenario!=NVS_MISSING && scenario!=NVS_UNAVAILABLE && scenario!=OTP_ERROR;
    if(calibrated) assert(hardware_vcom==0x46);
    else if(!early) assert(hardware_vcom==(scenario==SECOND ? 0x2e : 0x2d));
    assert(nvs_opens==(!early && scenario!=OTP_ERROR));
    assert(nvs_reads==(!early && scenario!=OTP_ERROR && scenario!=NVS_UNAVAILABLE));
    assert(nvs_closes==nvs_reads);
    printf("Display driver/BSP case %d RGB%d passed%s\n",scenario,bits,
           scenario==INIT_ERROR ? " (known BSP initialization-error masking observed)" : "");
}
'''

headers = (
    'driver/gpio.h', 'esp_check.h', 'esp_err.h', 'esp_lcd_mipi_dsi.h',
    'esp_lcd_panel_commands.h', 'esp_lcd_panel_io.h', 'esp_lcd_panel_ops.h',
    'esp_lcd_st7701.h', 'esp_ldo_regulator.h', 'esp_log.h', 'esp_timer.h',
    'esp_lcd_types.h', 'freertos/FreeRTOS.h', 'freertos/semphr.h',
    'freertos/task.h', 'freertos/idf_additions.h', 'freertos/projdefs.h',
    'sdkconfig.h', 'hal/mipi_dsi_hal.h', 'hal/gpio_types.h', 'hal/lcd_types.h',
    'bsp/device.h', 'bsp/tanmatsu.h', 'tanmatsu_coprocessor.h',
    'nvs.h',
)
with tempfile.TemporaryDirectory(prefix='sb-display-driver-') as tmp:
    path = Path(tmp)
    (path / 'mock.h').write_text(mock)
    for name in headers:
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('#include "mock.h"\n')
    (path / 'test.c').write_text(harness)
    subprocess.run([
        'cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
        '-fsanitize=undefined', '-include', str(path / 'mock.h'),
        '-I' + tmp, '-I' + str(bsp), '-I' + str(bsp / 'targets/tanmatsu'),
        '-I' + str(mipi / 'include'),
        str(mipi / 'dsi_panel_nicolaielectronics_st7701.c'),
        str(bsp / 'targets/tanmatsu/badge_bsp_display.c'), str(path / 'test.c'),
        '-Wl,--wrap=st7701_initialize', '-o', str(path / 'test'),
    ], check=True)
    for bits in (16, 24):
        for scenario in range(13):
            subprocess.run([str(path / 'test'), str(scenario), str(bits)], check=True)
