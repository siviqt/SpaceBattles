#!/usr/bin/env python3
"""Compile the vendored HAL read implementation against a simulated LCD FIFO."""
from pathlib import Path
import subprocess
import tempfile
root=Path(__file__).resolve().parents[1]
s=(root/'components/esp_hal_lcd/mipi_dsi_hal.c').read_text()
status=s[s.index('static bool s_gen_read_timed_out'):s.index('void mipi_dsi_hal_init(')]
read=s[s.index('void mipi_dsi_hal_host_gen_read_short_packet('):s.index('void mipi_dsi_hal_host_gen_read_dcs_command(')]
header=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define MIPI_DSI_HAL_GEN_READ_TIMEOUT_US 50000
#define MIPI_DSI_DT_SET_MAXIMUM_RETURN_PKT 0x37
#define MIPI_DSI_DT_DCS_READ_0 6
typedef int mipi_dsi_data_type_t;
typedef struct { void *host; } mipi_dsi_hal_context_t;
static int scenario,writes,words;
static int requested_size,requested_command;
static uint32_t payload;
static int64_t now;
static bool video,bta;
static int64_t esp_timer_get_time(void) { now+=1000; return now; }
static void mipi_dsi_hal_host_gen_write_short_packet(mipi_dsi_hal_context_t *h,int vc,int dt,int arg) {
 assert(h->host==(void*)1 && vc==0);assert(dt==(writes%2 ? 6 : 0x37));
 assert(arg==(writes%2 ? requested_command : requested_size));++writes;
}
static void mipi_dsi_host_ll_enable_video_mode(void *h,bool v) { (void)h;video=v; }
static void mipi_dsi_host_ll_enable_bta(void *h,bool v) { (void)h;bta=v; }
static void mipi_dsi_host_ll_gen_set_rx_vcid(void *h,int vc) { (void)h;assert(vc==0); }
static bool mipi_dsi_host_ll_gen_is_read_cmd_busy(void *h) { (void)h;return scenario==1; }
static bool mipi_dsi_host_ll_gen_is_read_fifo_empty(void *h) { (void)h;return scenario==2 || words>0; }
static uint32_t mipi_dsi_host_ll_gen_read_payload_fifo(void *h) { (void)h;++words;return payload; }
'''
main=r'''
int main(void) {
 mipi_dsi_hal_context_t h={.host=(void*)1};
 for(requested_size=1;requested_size<=3;requested_size+=2) {
  requested_command=requested_size==1 ? 0xb1 : 0x04;
  payload=requested_size==1 ? 0x1234562d : 0xab010042;
  for(int pass=0;pass<4;pass++) {
   scenario=pass==3 ? 0 : pass;words=0;now=0;video=true;bta=false;
   struct { uint8_t before,value[3],after; } out={0xa5,{0xff,0xff,0xff},0x5a};
   mipi_dsi_hal_host_gen_read_short_packet(&h,0,MIPI_DSI_DT_DCS_READ_0,requested_command,out.value,requested_size);
   assert(!video && bta && out.before==0xa5 && out.after==0x5a);
   assert(mipi_dsi_hal_host_gen_read_timed_out()==(scenario!=0));
   for(int i=0;i<3;i++) {
    uint8_t expected=i>=requested_size ? 0xff : scenario ? 0 : (payload>>(8*i))&0xff;
    assert(out.value[i]==expected);
   }
   if(scenario) assert(now>=50000 && now<55000 && !words);
   else assert(words==1 && now<50000);
  }
 }
 assert(writes==16);
 puts("LCD HAL passed: one-byte OTP and three-byte panel ID, both timeout paths, buffer guards and recovery");
}
'''
with tempfile.TemporaryDirectory(prefix='sb-hal-') as tmp:
 p=Path(tmp);(p/'test.c').write_text(header+status+read+main)
 subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
