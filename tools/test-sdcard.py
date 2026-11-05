#!/usr/bin/env python3
"""Exercise the resolved BSP storage and application worker against IDF mocks."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
bsp = root / 'managed_components/badgeteam__badge-bsp'
header = r'''
#pragma once
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CONFIG_BSP_TARGET_TANMATSU 1
#define CONFIG_ESP_HOSTED_SDIO_HOST_INTERFACE 1
#define CONFIG_ESP_HOSTED_SDIO_SLOT_1 1
#define CONFIG_ESP_HOSTED_SDIO_SLOT 1
#define CONFIG_ESP_HOSTED_SDIO_RESET_SLAVE_USING_CALLBACK 1
#define ESP_IDF_VERSION_VAL(a,b,c) ((a)*10000+(b)*100+(c))
#define ESP_IDF_VERSION ESP_IDF_VERSION_VAL(6,0,2)
#define ESP_OK 0
#define ESP_FAIL -1
#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_INVALID_ARG 0x102
#define ESP_ERR_NOT_FOUND 0x105
#define ESP_ERR_NOT_SUPPORTED 0x106
#define ESP_ERR_NO_MEM 0x101
#define ESP_ERR_TIMEOUT 0x107
#define SDMMC_HOST_SLOT_0 0
#define SDMMC_HOST_FLAG_DEINIT_ARG 1
#define SDMMC_FREQ_HIGHSPEED 40000
#define GPIO_MODE_OUTPUT_OD 1
#define GPIO_MODE_INPUT 2
#define GPIO_PULLUP_DISABLE 0
#define GPIO_PULLDOWN_DISABLE 0
#define GPIO_INTR_DISABLE 0
#define GPIO_NUM_39 39
#define GPIO_NUM_40 40
#define GPIO_NUM_41 41
#define GPIO_NUM_42 42
#define GPIO_NUM_43 43
#define GPIO_NUM_44 44
#define BIT64(n) (1ULL<<(n))
#define MALLOC_CAP_DMA 1
#define MALLOC_CAP_INTERNAL 2
#define BSP_INPUT_ACTION_TYPE_SD_CARD 0
#define WL_INVALID_HANDLE -1
#define SD_IO_RW_DIRECT 52
#define SCF_CMD_AC 1
#define SCF_RSP_R5 2
#define pdMS_TO_TICKS(n) (n)
#define pdTRUE 1
#define pdPASS 1
#define portMAX_DELAY 0xffffffffu
#define ESP_LOGI(...) ((void)0)
#define ESP_LOGD(...) ((void)0)
#define ESP_LOGW(...) ((void)0)
#define ESP_LOGE(...) ((void)0)
typedef int esp_err_t;
typedef int wl_handle_t;
typedef struct queue { size_t size; bool ready; unsigned char data[8]; } *QueueHandle_t;
typedef void *TaskHandle_t;
typedef void *sd_pwr_ctrl_handle_t;
typedef struct { int ldo_chan_id; } sd_pwr_ctrl_ldo_config_t;
typedef struct { uint64_t pin_bit_mask; int mode,pull_up_en,pull_down_en,intr_type; } gpio_config_t;
typedef struct { int unused; } sdmmc_card_t;
typedef struct { int opcode,arg,flags,timeout_ms; } sdmmc_command_t;
typedef struct {
 int slot,flags,max_freq_khz;
 esp_err_t (*init)(void);
 union { esp_err_t (*deinit)(void); esp_err_t (*deinit_p)(int); };
 void *pwr_ctrl_handle,*dma_aligned_buffer;
} sdmmc_host_t;
typedef struct { int clk,cmd,d0,d1,d2,d3,width; } sdmmc_slot_config_t;
typedef struct { bool format_if_mount_failed; int max_files,allocation_unit_size; } esp_vfs_fat_sdmmc_mount_config_t;
int sdmmc_host_init(void);
int sdmmc_host_deinit(void);
int sdmmc_host_deinit_slot(int);
int sdmmc_host_do_transaction(int,sdmmc_command_t *);
#define SDMMC_HOST_DEFAULT() ((sdmmc_host_t){.init=sdmmc_host_init,.flags=SDMMC_HOST_FLAG_DEINIT_ARG,.deinit_p=sdmmc_host_deinit_slot})
#define SDMMC_SLOT_CONFIG_DEFAULT() ((sdmmc_slot_config_t){0})
int gpio_config(const gpio_config_t *);
int gpio_set_level(int,int);
int sd_pwr_ctrl_new_on_chip_ldo(const sd_pwr_ctrl_ldo_config_t *,sd_pwr_ctrl_handle_t *);
int sd_pwr_ctrl_set_io_voltage(void *,int);
void *heap_caps_malloc(size_t,int);
int bsp_input_read_action(int,bool *);
int esp_vfs_fat_sdmmc_mount(const char *,const sdmmc_host_t *,const sdmmc_slot_config_t *,const esp_vfs_fat_sdmmc_mount_config_t *,sdmmc_card_t **);
int esp_vfs_fat_sdcard_unmount(const char *,sdmmc_card_t *);
int esp_vfs_fat_sdcard_format(const char *,sdmmc_card_t *);
void vTaskDelay(unsigned);
void vTaskDelete(void *);
int xTaskCreate(void (*)(void *),const char *,unsigned,void *,unsigned,void **);
QueueHandle_t xQueueCreate(unsigned,unsigned);
int xQueueSend(QueueHandle_t,const void *,unsigned);
int xQueueReceive(QueueHandle_t,void *,unsigned);
void vQueueDelete(QueueHandle_t);
'''
harness = r'''
#include "bsp_storage_under_test.c"
#include "platform/sdcard.c"
static int scenario,last_slot=1;
static bool sd_slot,stall;
static unsigned ldo_acquires,cmd52s,deinits,mounts,unmounts,deleted,queue_calls;
static sdmmc_host_t mounted_host;
static sdmmc_card_t mock_card;
static void (*scheduled)(void *);
static int release(const sdmmc_host_t *h) {
 assert(h->flags & SDMMC_HOST_FLAG_DEINIT_ARG); return h->deinit_p(h->slot);
}
int sdmmc_host_init(void) { assert(!"duplicate shared-controller initialization"); return ESP_FAIL; }
int sdmmc_host_deinit(void) { assert(!"whole-controller deinit would remove Hosted"); return ESP_FAIL; }
int sdmmc_host_do_transaction(int slot,sdmmc_command_t *cmd) {
 assert(slot==1 && cmd->opcode==52 && cmd->arg==0 && cmd->timeout_ms==1000);
 last_slot=1; ++cmd52s; return ESP_OK;
}
int sdmmc_host_deinit_slot(int slot) {
 assert(slot==0 && last_slot==1); sd_slot=false; ++deinits; return ESP_OK;
}
int gpio_config(const gpio_config_t *p) { assert(p->pin_bit_mask); return ESP_OK; }
int gpio_set_level(int p,int v) { assert(p>=39 && p<=44 && v==0); return ESP_OK; }
int sd_pwr_ctrl_new_on_chip_ldo(const sd_pwr_ctrl_ldo_config_t *p,void **out) {
 assert(p->ldo_chan_id==4 && ++ldo_acquires==1); *out=(void*)4; return ESP_OK;
}
int sd_pwr_ctrl_set_io_voltage(void *p,int v) { assert(p==(void*)4 && (v==0 || v==3300)); return ESP_OK; }
void *heap_caps_malloc(size_t n,int caps) { assert(n==2048 && caps==(MALLOC_CAP_DMA|MALLOC_CAP_INTERNAL)); return malloc(n); }
int bsp_input_read_action(int a,bool *out) { assert(a==0); *out=scenario!=1; return ESP_OK; }
int esp_vfs_fat_sdmmc_mount(const char *p,const sdmmc_host_t *h,const sdmmc_slot_config_t *slot,const esp_vfs_fat_sdmmc_mount_config_t *cfg,sdmmc_card_t **out) {
 ++mounts; assert(!strcmp(p,"/sd") && h->slot==0 && slot->width==4);
 assert(slot->clk==43 && slot->cmd==44 && slot->d0==39 && slot->d3==42);
 assert(h->pwr_ctrl_handle==(void*)4 && h->dma_aligned_buffer && h->init()==ESP_OK);
 assert(!cfg->format_if_mount_failed && cfg->max_files==4 && cfg->allocation_unit_size==16384);
 if(scenario==1) return ESP_ERR_NOT_FOUND;
 sd_slot=true; last_slot=0;
 if(scenario==2) { assert(release(h)==ESP_OK); return ESP_ERR_TIMEOUT; }
 mounted_host=*h; *out=&mock_card; return ESP_OK;
}
int esp_vfs_fat_sdcard_unmount(const char *p,sdmmc_card_t *c) {
 ++unmounts; assert(!strcmp(p,"/sd") && c==&mock_card); assert(release(&mounted_host)==ESP_OK);
 return scenario==3 ? ESP_FAIL : ESP_OK;
}
int esp_vfs_fat_sdcard_format(const char *p,sdmmc_card_t *c) { (void)p;(void)c;assert(!"format must not be called");return ESP_FAIL; }
void vTaskDelay(unsigned n) { (void)n; }
void vTaskDelete(void *task) { if(task) ++deleted; }
int xTaskCreate(void (*fn)(void *),const char *n,unsigned stack,void *arg,unsigned pri,void **out) {
 (void)n;(void)arg;assert(stack==4096 && pri==4);
 if(scenario==8) return 0;
 scheduled=fn;*out=(void*)1;return pdPASS;
}
QueueHandle_t xQueueCreate(unsigned count,unsigned size) {
 assert(count==1 && size<=8); ++queue_calls;
 if(scenario==7 && queue_calls==2) return NULL;
 QueueHandle_t q=calloc(1,sizeof(*q)); assert(q);q->size=size;return q;
}
int xQueueSend(QueueHandle_t q,const void *p,unsigned timeout) {
 (void)timeout; if(scenario==6 && q==requests) return 0;
 assert(!q->ready);memcpy(q->data,p,q->size);q->ready=true;return pdTRUE;
}
int xQueueReceive(QueueHandle_t q,void *p,unsigned timeout) {
 if(q==results && !q->ready) {
  assert(timeout==8000 || timeout==2000);
  if(stall) return 0;
  scheduled(NULL);
 }
 if(!q->ready) return 0;
 memcpy(p,q->data,q->size);q->ready=false;return pdTRUE;
}
void vQueueDelete(QueueHandle_t q) { free(q); }
int main(int argc,char **argv) {
 assert(argc==2);scenario=atoi(argv[1]);
 assert(bsp_storage_initialize()==ESP_OK && ldo_acquires==1);
 stall=scenario==4;
 sb_sd_mount_result_t r=sb_platform_sd_mount();
 if(scenario==7 || scenario==8) { assert(r.error==ESP_ERR_NO_MEM && !r.worker_pending && !requests && !results); }
 else if(scenario==6) { assert(r.error==ESP_ERR_INVALID_STATE && !r.worker_pending);assert(sb_platform_sd_shutdown()==ESP_ERR_INVALID_STATE && !requests); }
 else if(scenario==4) {
  assert(r.error==ESP_ERR_TIMEOUT && r.worker_pending && !mounts);
  assert(sb_platform_sd_shutdown()==ESP_ERR_INVALID_STATE && !deleted && requests && results);
 } else {
  assert(r.error==(scenario==1 ? ESP_ERR_NOT_FOUND : scenario==2 ? ESP_ERR_TIMEOUT : ESP_OK));
  assert(!r.worker_pending && ldo_acquires==1);
  stall=scenario==5;
  int err=sb_platform_sd_shutdown();
  if(scenario==5) {
   assert(err==ESP_ERR_TIMEOUT && worker_busy && !deleted && requests && results && sd_slot);
   assert(sb_platform_sd_shutdown()==ESP_ERR_INVALID_STATE);
  } else if(scenario==3) {
   assert(err==ESP_FAIL && cleanup_failed && deleted==1 && !requests);
   assert(sb_platform_sd_mount().error==ESP_ERR_INVALID_STATE && unmounts==1);
   assert(unmount_card()==ESP_ERR_INVALID_STATE && unmounts==1);
  } else {
   assert(err==ESP_OK && !sd_slot && deleted==1 && !requests);
   assert(cmd52s==(scenario==1 ? 0u : 1u) && deinits==cmd52s);
   assert(sb_platform_sd_shutdown()==ESP_OK);
   if(!scenario) for(int i=0;i<2;i++) {
    assert(sb_platform_sd_mount().error==ESP_OK);assert(sb_platform_sd_shutdown()==ESP_OK);
    assert(ldo_acquires==1 && !sd_slot && last_slot==1);
   }
  }
 }
 free(sd_dma_buf); // BSP retains DMA until restart; free only in this host process.
 if(requests) free(requests);if(results) free(results);
 printf("BSP SD integration scenario %d passed\n",scenario);
}
'''
with tempfile.TemporaryDirectory(prefix='sb-sdcard-') as tmp:
    p=Path(tmp)
    (p/'mock.h').write_text(header)
    for name in ('esp_err.h','sdkconfig.h','bsp/input.h','driver/gpio.h','driver/sdmmc_host.h','esp_heap_caps.h','esp_log.h','esp_idf_version.h','esp_vfs.h','esp_vfs_fat.h','hal/gpio_types.h','sd_protocol_defs.h','sd_pwr_ctrl.h','sd_pwr_ctrl_by_on_chip_ldo.h','sdmmc_cmd.h','freertos/FreeRTOS.h','freertos/queue.h','freertos/task.h'):
        dest=p/name;dest.parent.mkdir(exist_ok=True,parents=True);dest.write_text('#include "mock.h"\n')
    (p/'bsp_storage_under_test.c').write_text((bsp/'targets/tanmatsu/badge_bsp_storage.c').read_text())
    (p/'test.c').write_text(harness)
    exe=p/'test'
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-Wno-unused-variable','-Wno-misleading-indentation','-fsanitize=undefined','-I'+tmp,'-I'+str(bsp),'-I'+str(root/'components/spacebattles'),str(p/'test.c'),'-o',str(exe)],check=True)
    for scenario in range(9): subprocess.run([str(exe),str(scenario)],check=True)
