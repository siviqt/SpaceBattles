// SPDX-License-Identifier: MIT
#include "platform/sdcard.h"
#include "bsp/storage.h"
#include "esp_log.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#if !defined(CONFIG_BSP_TARGET_TANMATSU)
#error "SD wiring is validated only for the Tanmatsu target"
#endif
#if defined(CONFIG_ESP_HOSTED_SDIO_HOST_INTERFACE) && (!defined(CONFIG_ESP_HOSTED_SDIO_SLOT_1) || !defined(CONFIG_ESP_HOSTED_SDIO_RESET_SLAVE_USING_CALLBACK))
#error "Multiplayer radio requires slot 1 and the Tanmatsu reset callback"
#endif

static QueueHandle_t requests, results;
static TaskHandle_t worker;
static bool worker_busy;
// BSP owns the SD power, DMA buffer and shared SDMMC controller.
// Only the worker calls storage APIs. A cleanup error is terminal: the BSP
// may retain a card pointer after IDF has freed it, so never retry before reset.
static bool cleanup_failed;

static esp_err_t mount_card(void) {
    if (cleanup_failed) return ESP_ERR_INVALID_STATE;
    return bsp_storage_mount_advanced(BSP_STORAGE_TYPE_SDCARD, "/sd", 4, false);
}

static esp_err_t unmount_card(void) {
    if (cleanup_failed) return ESP_ERR_INVALID_STATE;
    esp_err_t err = bsp_storage_unmount(BSP_STORAGE_TYPE_SDCARD);
    if (err != ESP_OK) cleanup_failed = true;
    return err;
}

static void sd_worker(void *unused) {
    (void)unused;
    bool mount;
    while (xQueueReceive(requests, &mount, portMAX_DELAY) == pdTRUE) {
        esp_err_t err = mount ? mount_card() : unmount_card();
        if (err != ESP_OK) ESP_LOGW("Storage", "SD %s failed: %s", mount ? "mount" : "cleanup", esp_err_to_name(err));
        else ESP_LOGD("Storage", "SD %s complete", mount ? "mount" : "cleanup");
        xQueueSend(results, &err, portMAX_DELAY);
    }
    vTaskDelete(NULL);
}

static esp_err_t request(bool mount, unsigned timeout_ms) {
    if (worker_busy) return ESP_ERR_INVALID_STATE;
    worker_busy = true;
    if (xQueueSend(requests, &mount, 0) != pdTRUE) {
        worker_busy = false;
        return ESP_ERR_INVALID_STATE;
    }
    esp_err_t err;
    if (xQueueReceive(results, &err, pdMS_TO_TICKS(timeout_ms)) != pdTRUE) {
        ESP_LOGE("M0a", "SD worker deadline exceeded; retain resources until restart");
        return ESP_ERR_TIMEOUT;
    }
    worker_busy = false;
    return err;
}

sb_sd_mount_result_t sb_platform_sd_mount(void) {
    if (cleanup_failed) return (sb_sd_mount_result_t){ESP_ERR_INVALID_STATE, false};
    if (requests) return (sb_sd_mount_result_t){ESP_ERR_INVALID_STATE, worker_busy};
    requests = xQueueCreate(1, sizeof(bool));
    results = xQueueCreate(1, sizeof(esp_err_t));
    if (!requests || !results || xTaskCreate(sd_worker, "sb_sd", 4096, NULL, 4, &worker) != pdPASS) {
        if (requests) vQueueDelete(requests);
        if (results) vQueueDelete(results);
        requests = results = NULL;
        ESP_LOGE("Storage", "Unable to allocate SD worker resources");
        return (sb_sd_mount_result_t){ESP_ERR_NO_MEM, false};
    }
    esp_err_t err = request(true, 8000);
    return (sb_sd_mount_result_t){err, worker_busy};
}

esp_err_t sb_platform_sd_shutdown(void) {
    if (!requests) return ESP_OK;
    // Do not cancel a driver operation or free resources underneath it.
    if (worker_busy) return ESP_ERR_INVALID_STATE;
    esp_err_t err = request(false, 2000);
    if (!worker_busy) {
        // The reply confirms the driver call returned. Stop the now-idle worker
        // before deleting its queues; a timed-out worker stays alive until reset.
        vTaskDelete(worker);
        worker = NULL;
        vQueueDelete(requests);
        vQueueDelete(results);
        requests = results = NULL;
    }
    return err;
}
