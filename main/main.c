#include <stdlib.h>
#include <time.h>
#include "esp_log.h"
#include "cJSON.h"
#include "esp_heap_caps.h"
#include "esp_system.h"
#include "nvs_flash.h"
#include "waveshare_rgb_lcd_port.h"
#include "lvgl.h"

#include "airports.h"
#include "flight_task.h"
#include "logos.h"
#include "settings.h"
#include "input_ctl.h"
#include "tilemap.h"
#include "ui.h"
#include "ui_settings.h"
#include "ui_map.h"
#include "web_server.h"
#include "wifi_mgr.h"
#include "esp_flash.h"
#include "esp_psram.h"
#include "observer_config.h"
#include "tz.h"

static const char *TAG = "canflight";

static void *psram_prefer_malloc(size_t n)
{
    return heap_caps_malloc_prefer(n, 2,
                                   MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT,
                                   MALLOC_CAP_8BIT);
}

static void backlight_after_first_frame(lv_timer_t *t)
{
    (void)t;
    waveshare_rgb_lcd_bl_on();
    if (settings_get()->brightness_ctl && settings_get()->brightness < 100 &&
        waveshare_rgb_lcd_bl_dimmable()) {
        waveshare_rgb_lcd_bl_pct(settings_get()->brightness);
    }
}

void app_main(void)
{
    /* first thing in the log after any spontaneous restart: why it happened */
    ESP_LOGW("boot", "reset reason: %d (4=panic 5=int_wdt 6=task_wdt 7=other_wdt 9=brownout)",
             (int)esp_reset_reason());
    /* POSIX TZ uses the inverse sign: ICT-7 = Asia/Ho_Chi_Minh, UTC+7.
     * The observer's fetched timezone remains authoritative after startup. */
    setenv("TZ", OBSERVER_DEFAULT_TZ, 1);
    tzset();
    tz_set_home_offset(OBSERVER_DEFAULT_UTC_OFFSET);

    uint32_t flash_bytes = 0;
    ESP_ERROR_CHECK(esp_flash_get_size(NULL, &flash_bytes));
    ESP_LOGI("boot", "physical flash=%lu bytes; PSRAM=%u bytes; local LCD-7 N8R8 profile",
             (unsigned long)flash_bytes, (unsigned)esp_psram_get_size());
    if (flash_bytes != 8 * 1024 * 1024 || esp_psram_get_size() < 8 * 1024 * 1024) {
        ESP_LOGE("boot", "Hardware capacity mismatch; startup stopped without erasing data");
        return;
    }

    /* cJSON trees (state JSON, API parses) are large and transient:
     * keep them out of the scarce internal heap. */
    cJSON_Hooks jh = { .malloc_fn = psram_prefer_malloc, .free_fn = free };
    cJSON_InitHooks(&jh);

    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_LOGE(TAG, "NVS requires recovery (%s); refusing automatic erase", esp_err_to_name(err));
        return;
    }
    ESP_ERROR_CHECK(err);
    settings_load();

    ESP_ERROR_CHECK(waveshare_esp32_s3_rgb_lcd_init());

    logos_init();
    airports_init();
    tilemap_init();
    /* Keep the small route fallback hot. With three rotated RGB buffers,
     * reserve the large map's 640 KB until the full-screen map is opened. */
#if !CONFIG_CANFLIGHT_WAVESHARE7_KNOWN_GOOD
    ui_map_get_image();
#endif
    ui_map_get_image_small();

    if (lvgl_port_lock(-1)) {
        ui_init();
        /* flight_task supplies home after Wi-Fi/netif initialization, so
         * the default radar cannot start a tile fetch before lwIP is ready. */
        if (settings_get()->wifi_ssid[0] == '\0') {
            ui_settings_open();   /* first boot: land straight in setup */
        }
        /* Light the panel only once it shows the first real frame: an
         * early bl_on lit an empty framebuffer, the white flash at every
         * boot. A one-shot LVGL timer runs in the LVGL task after its
         * first refresh. (Never lv_refr_now() from here: the RGB flush
         * waits for a vsync notification addressed to the LVGL task and
         * would block app_main forever.) */
        lv_timer_t *blt = lv_timer_create(backlight_after_first_frame, 250, NULL);
        lv_timer_set_repeat_count(blt, 1);
        lvgl_port_unlock();
    }

    err = wifi_mgr_start();
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "Wi-Fi init failed: %s", esp_err_to_name(err));
    }

    input_ctl_init();
    web_server_start();
    flight_task_start();
}
