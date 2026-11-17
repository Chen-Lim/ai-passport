#include "travel_demo.h"
#include "travel_ui.h"

#include "bsp_audio.h"
#include "bsp_battery.h"
#include "bsp_button.h"
#include "bsp_display.h"
#include "bsp_i2c.h"
#include "esp_log.h"
#include "esp_heap_caps.h"
#include "esp_pm.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "sdkconfig.h"

static const char *TAG = "travel";
static QueueHandle_t s_commands;

typedef struct { bsp_btn_t button; bsp_btn_ev_t event; } travel_command_t;

static void on_key(bsp_btn_t button, bsp_btn_ev_t event, void *user)
{
    (void)user;
    /* The shared esp_timer callback only dispatches bounded, nonblocking work. */
    if (event != BSP_BTN_CLICK && event != BSP_BTN_LONG && event != BSP_BTN_DOUBLE) return;
    const travel_command_t command = {.button = button, .event = event};
    if (s_commands) (void)xQueueSend(s_commands, &command, 0);
}

void app_main(void)
{
    ESP_LOGI(TAG, "Travel Pocket: loaded static train itinerary G7687");
#if CONFIG_PM_ENABLE
    const esp_pm_config_t power = {
        .max_freq_mhz = 160, .min_freq_mhz = 40, .light_sleep_enable = true,
    };
    esp_err_t power_error = esp_pm_configure(&power);
    if (power_error != ESP_OK) ESP_LOGW(TAG, "Power management unavailable: %s", esp_err_to_name(power_error));
#endif
    if (bsp_display_init() != ESP_OK || !bsp_lvgl_init()) {
        ESP_LOGE(TAG, "Display initialization failed");
        return;
    }
    bsp_display_backlight(0);
    /* No audio feature: suspend the codec without recording or allocating PCM. */
    if (bsp_audio_init() == ESP_OK) {
        esp_err_t audio_error = bsp_audio_sleep();
        if (audio_error != ESP_OK) ESP_LOGW(TAG, "Codec suspend failed: %s", esp_err_to_name(audio_error));
    }
    bool battery_available = bsp_battery_init() == ESP_OK;
    travel_state_t state;
    travel_state_init(&state);
    int64_t boot_time = esp_timer_get_time();
    travel_demo_load(&state, TRAVEL_DEMO_NORMAL, INT64_C(1794915600));
    state.clock_valid = false;

    if (!bsp_lvgl_lock(1000)) return;
    bool ui_ready = travel_ui_create();
    if (ui_ready) travel_ui_update(&state, INT64_C(1794915600), -1, NULL);
    bsp_lvgl_unlock();
    if (!ui_ready) {
        ESP_LOGE(TAG, "UI font coverage check failed");
        return;
    }
    bsp_display_backlight(65);
    s_commands = xQueueCreate(12, sizeof(travel_command_t));
    esp_err_t button_error = s_commands ? bsp_button_init(on_key, NULL) : ESP_ERR_NO_MEM;
    if (button_error != ESP_OK) ESP_LOGW(TAG, "Buttons unavailable: %s", esp_err_to_name(button_error));

    int64_t last_activity = boot_time;
    int64_t last_render = 0;
    int64_t last_battery = boot_time;
    int battery_soc = battery_available ? bsp_battery_soc() : -1;
    unsigned brightness = 65;
    for (;;) {
        travel_command_t command;
        bool received = s_commands
                      ? xQueueReceive(s_commands, &command, pdMS_TO_TICKS(200)) == pdTRUE
                      : false;
        if (!s_commands) vTaskDelay(pdMS_TO_TICKS(200));
        int64_t monotonic = esp_timer_get_time();
        int64_t now = INT64_C(1794915600) + (monotonic - boot_time) / INT64_C(1000000);
        bool changed = false;
        if (received) {
            bool wake_only = brightness == 0;
            last_activity = monotonic;
            if (!wake_only) {
                if (command.button == BSP_BTN_OK && command.event == BSP_BTN_LONG) {
                    (void)travel_state_action(&state, TRAVEL_BACK, false);
                } else if (command.event == BSP_BTN_CLICK || command.event == BSP_BTN_DOUBLE) {
                    if (command.button == BSP_BTN_UP) (void)travel_state_action(&state, TRAVEL_PREVIOUS, false);
                    if (command.button == BSP_BTN_DOWN) (void)travel_state_action(&state, TRAVEL_NEXT, false);
                    if (command.button == BSP_BTN_OK) (void)travel_state_action(&state, TRAVEL_CONFIRM, false);
                }
                changed = true;
            }
        }
        int64_t idle = monotonic - last_activity;
        unsigned target = travel_idle_backlight(idle);
        if (target != brightness) {
            bsp_display_backlight((uint8_t)target);
            brightness = target;
            changed = true;
        }
        if (battery_available && monotonic - last_battery >= INT64_C(30000000)) {
            /* I2C reads run outside the LVGL lock and outside button callbacks. */
            battery_soc = bsp_battery_soc();
            last_battery = monotonic;
            ESP_LOGI(TAG, "Heap free=%u minimum=%u largest=%u stack=%u",
                     (unsigned)heap_caps_get_free_size(MALLOC_CAP_8BIT),
                     (unsigned)heap_caps_get_minimum_free_size(MALLOC_CAP_8BIT),
                     (unsigned)heap_caps_get_largest_free_block(MALLOC_CAP_8BIT),
                     (unsigned)uxTaskGetStackHighWaterMark(NULL));
            changed = true;
        }
        if (brightness && (changed || monotonic - last_render >= INT64_C(1000000))) {
            if (bsp_lvgl_lock(200)) {
                travel_ui_update(&state, now, battery_soc, button_error == ESP_OK ? NULL : "按键不可用");
                bsp_lvgl_unlock();
                last_render = monotonic;
            }
        }
    }
}
