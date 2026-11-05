#!/usr/bin/env python3
"""Exercise real platform startup, NVS fallback and LCD completion ownership."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
header=r'''
#pragma once
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#define SB_COLOR_BITS 16
#define SB_PERFORMANCE 0
#define SB_VALIDATION_NAME "none"
#define IRAM_ATTR
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_NOT_SUPPORTED 1
#define ESP_ERR_INVALID_STATE 2
#define ESP_ERR_NO_MEM 3
#define ESP_ERR_TIMEOUT 4
#define BSP_DISPLAY_COLOR_FORMAT_16_565RGB 16
#define BSP_DISPLAY_COLOR_FORMAT_24_888RGB 24
#define BSP_DISPLAY_ENDIAN_BIG 1
#define BSP_DISPLAY_ROTATION_0 0
#define BSP_DISPLAY_ROTATION_90 1
#define BSP_DISPLAY_ROTATION_180 2
#define BSP_DISPLAY_ROTATION_270 3
#define pdFALSE 0
#define pdTRUE 1
#define pdMS_TO_TICKS(n) (n)
#define ESP_LOGI(...) test_log(__VA_ARGS__)
#define ESP_LOGD(...) test_log(__VA_ARGS__)
#define ESP_LOGE(...) test_log(__VA_ARGS__)
#define ESP_LOGW(...) test_log(__VA_ARGS__)
typedef int esp_err_t;
typedef int bsp_display_color_format_t;
typedef int bsp_display_endianness_t;
typedef int BaseType_t;
typedef void *esp_lcd_panel_handle_t;
typedef void *SemaphoreHandle_t;
typedef void *tanmatsu_coprocessor_handle_t;
typedef struct { unsigned revision; } esp_chip_info_t;
typedef struct { const char *project_name,*version; } esp_app_desc_t;
typedef struct { int requested_color_format,num_fbs; } bsp_display_configuration_t;
typedef struct { bsp_display_configuration_t display; } bsp_configuration_t;
typedef struct { int unused; } esp_lcd_dpi_panel_event_data_t;
typedef struct { bool (*on_color_trans_done)(esp_lcd_panel_handle_t,esp_lcd_dpi_panel_event_data_t *,void *); } esp_lcd_dpi_panel_event_callbacks_t;
void test_log(const char *,const char *,...);
void esp_chip_info(esp_chip_info_t *);
const char *esp_get_idf_version(void);
const char *esp_err_to_name(int);
const esp_app_desc_t *esp_app_get_description(void);
int64_t esp_timer_get_time(void);
int nvs_flash_init(void);
int bsp_device_initialize(const bsp_configuration_t *);
int bsp_tanmatsu_coprocessor_get_handle(void **);
int tanmatsu_coprocessor_get_firmware_version(void *,uint16_t *);
int bsp_display_get_parameters(size_t *,size_t *,int *,int *);
int bsp_display_get_default_rotation(void);
int bsp_display_get_panel(void **);
int esp_lcd_dpi_panel_register_event_callbacks(void *,const esp_lcd_dpi_panel_event_callbacks_t *,void *);
int esp_lcd_panel_draw_bitmap(void *,int,int,int,int,const void *);
SemaphoreHandle_t xSemaphoreCreateBinary(void);
void vSemaphoreDelete(void *);
int xSemaphoreGive(void *);
int xSemaphoreGiveFromISR(void *,int *);
int xSemaphoreTake(void *,unsigned);
bool xPortInIsrContext(void);
'''
harness=r'''
#include "platform/tanmatsu.c"
static int scenario,nvs_calls,bsp_calls,cop_calls,gives,deletes;
static bool token;
static esp_lcd_dpi_panel_event_callbacks_t registered;
static void *registered_context;
void test_log(const char *tag,const char *fmt,...) { (void)tag;(void)fmt; }
void esp_chip_info(esp_chip_info_t *c) { c->revision=1; }
const char *esp_get_idf_version(void) { return "6.0.2"; }
const char *esp_err_to_name(int e) { (void)e;return "test"; }
const esp_app_desc_t *esp_app_get_description(void) { static const esp_app_desc_t d={"spacebattles","6"};return &d; }
int64_t esp_timer_get_time(void) { static int64_t t;return ++t; }
int nvs_flash_init(void) { assert(!bsp_calls);++nvs_calls;return scenario==1 ? ESP_FAIL : ESP_OK; }
int bsp_device_initialize(const bsp_configuration_t *c) {
 assert(nvs_calls==1 && c->display.requested_color_format==16 && c->display.num_fbs==1);++bsp_calls;
 return scenario==2 ? ESP_FAIL : ESP_OK;
}
int bsp_tanmatsu_coprocessor_get_handle(void **h) { ++cop_calls;*h=(void*)2;return ESP_OK; }
int tanmatsu_coprocessor_get_firmware_version(void *h,uint16_t *v) { assert(h==(void*)2);*v=8;return ESP_OK; }
int bsp_display_get_parameters(size_t *w,size_t *h,int *f,int *e) { *w=480;*h=800;*f=scenario==3 ? 24 : 16;*e=1;return ESP_OK; }
int bsp_display_get_default_rotation(void) { return scenario==4 ? 99 : BSP_DISPLAY_ROTATION_90; }
int bsp_display_get_panel(void **h) { *h=scenario==5 ? NULL : (void*)3;return ESP_OK; }
SemaphoreHandle_t xSemaphoreCreateBinary(void) { return scenario==6 ? NULL : (void*)4; }
void vSemaphoreDelete(void *h) { assert(h==(void*)4);++deletes; }
int esp_lcd_dpi_panel_register_event_callbacks(void *h,const esp_lcd_dpi_panel_event_callbacks_t *c,void *ctx) {
 assert(h==(void*)3 && ctx==(void*)4);registered=*c;registered_context=ctx;return scenario==7 ? ESP_FAIL : ESP_OK;
}
int esp_lcd_panel_draw_bitmap(void *h,int x,int y,int w,int height,const void *p) {
 assert(h==(void*)3 && !x && !y && w==480 && height==800 && p==(void*)5);
 if(scenario==8) return ESP_FAIL;
 if(scenario!=9) registered.on_color_trans_done(h,NULL,registered_context);
 return ESP_OK;
}
int xSemaphoreGive(void *h) { assert(h==(void*)4);token=true;++gives;return pdTRUE; }
int xSemaphoreGiveFromISR(void *h,int *wake) { *wake=pdTRUE;return xSemaphoreGive(h); }
int xSemaphoreTake(void *h,unsigned timeout) { assert(h==(void*)4 && timeout==1000);bool v=token;token=false;return v; }
bool xPortInIsrContext(void) { return scenario==10; }
int main(int argc,char **argv) {
 assert(argc==2);scenario=atoi(argv[1]);
 assert(sb_platform_init()==(scenario==2 ? ESP_FAIL : ESP_OK));
 assert(cop_calls==(scenario==2 ? 0 : 1));
 sb_display_t d={0};int err=sb_platform_display_init(&d);
 if(scenario==3 || scenario==4) assert(err==ESP_ERR_NOT_SUPPORTED);
 else if(scenario==5) assert(err==ESP_ERR_INVALID_STATE);
 else if(scenario==6) assert(err==ESP_ERR_NO_MEM);
 else if(scenario==7) assert(err==ESP_FAIL && deletes==1 && !transfer_done);
 else {
  assert(err==ESP_OK && d.width==480 && d.height==800 && d.rotation==90 && d.big_endian);
  assert(sb_platform_can_release_frame());
  err=sb_platform_present((void*)5);
  assert(err==(scenario==8 ? ESP_FAIL : scenario==9 ? ESP_ERR_TIMEOUT : ESP_OK));
  assert(sb_platform_can_release_frame()==(scenario!=8 && scenario!=9));
  if(scenario==8 || scenario==9) assert(sb_platform_present((void*)5)==ESP_ERR_INVALID_STATE);
  else { assert(gives==1);assert(sb_platform_present((void*)5)==ESP_OK && gives==2); }
 }
 printf("Platform startup/display scenario %d passed\n",scenario);
}
'''
with tempfile.TemporaryDirectory(prefix='sb-platform-') as tmp:
 p=Path(tmp);(p/'mock.h').write_text(header+'\n#include <stdlib.h>\n')
 for name in ('validation/performance.h','bsp/device.h','bsp/display.h','bsp/tanmatsu.h','esp_app_desc.h','esp_chip_info.h','esp_timer.h','esp_attr.h','esp_lcd_mipi_dsi.h','esp_lcd_panel_ops.h','esp_log.h','nvs_flash.h','esp_err.h','freertos/FreeRTOS.h','freertos/semphr.h','freertos/task.h'):
  dest=p/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text('#include "mock.h"\n')
 (p/'test.c').write_text(harness)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined','-I'+tmp,'-I'+str(root/'components/spacebattles'),str(p/'test.c'),'-o',str(p/'test')],check=True)
 for scenario in range(11):subprocess.run([str(p/'test'),str(scenario)],check=True)
