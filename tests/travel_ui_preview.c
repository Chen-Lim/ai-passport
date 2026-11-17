/* Native LVGL rendering probe; no ESP-IDF or USB access is used. */
#include "travel_demo.h"
#include "travel_ui.h"
#include "bsp_pins.h"
#include "lvgl.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint16_t s_pixels[BSP_LCD_W * BSP_LCD_H];
static uint16_t s_buffer[BSP_LCD_W * BSP_LCD_H];
static unsigned s_flushes;

#ifdef TRAVEL_PREVIEW_INPUT
#include "travel_input.h"
#endif

static void flush(lv_display_t *display, const lv_area_t *area, uint8_t *pixels)
{
    const uint16_t *input = (const uint16_t *)pixels;
    for (int y = area->y1; y <= area->y2; ++y) {
        for (int x = area->x1; x <= area->x2; ++x) {
            s_pixels[y * BSP_LCD_W + x] = *input++;
        }
    }
    ++s_flushes;
    lv_display_flush_ready(display);
}

static void inspect(lv_obj_t *object)
{
    if (lv_obj_has_flag(object, LV_OBJ_FLAG_HIDDEN)) return;
    if (lv_obj_check_type(object, &lv_label_class)) {
        const char *value = lv_label_get_text(object);
        assert(strcmp(value, "文字不支持") != 0);
        lv_point_t size;
        lv_text_get_size(&size, value, lv_obj_get_style_text_font(object, LV_PART_MAIN),
                         0, 0, LV_COORD_MAX, LV_TEXT_FLAG_NONE);
        assert(size.x <= lv_obj_get_width(object));
        lv_obj_t *parent = lv_obj_get_parent(object);
        assert(lv_obj_get_y(object) + size.y <= lv_obj_get_height(parent));
    }
    for (uint32_t i = 0; i < lv_obj_get_child_count(object); ++i) inspect(lv_obj_get_child(object, i));
}

static void save(const char *directory, int scenario, int ticket, int details)
{
    char path[1024];
    snprintf(path, sizeof(path), "%s/scenario-%d-ticket-%d-details-%d.ppm", directory, scenario, ticket, details);
    FILE *file = fopen(path, "wb");
    assert(file);
    fprintf(file, "P6\n%d %d\n255\n", BSP_LCD_W, BSP_LCD_H);
    for (size_t i = 0; i < BSP_LCD_W * BSP_LCD_H; ++i) {
        uint16_t pixel = s_pixels[i];
        unsigned char rgb[3] = {
            (unsigned char)(((pixel >> 11) & 31) * 255 / 31),
            (unsigned char)(((pixel >> 5) & 63) * 255 / 63),
            (unsigned char)((pixel & 31) * 255 / 31),
        };
        assert(fwrite(rgb, 1, 3, file) == 3);
    }
    fclose(file);
}

int main(int argc, char **argv)
{
    assert(argc == 2);
    lv_init();
    lv_display_t *display = lv_display_create(BSP_LCD_W, BSP_LCD_H);
    assert(display);
    lv_display_set_color_format(display, LV_COLOR_FORMAT_RGB565);
    lv_display_set_buffers(display, s_buffer, NULL, sizeof(s_buffer), LV_DISPLAY_RENDER_MODE_FULL);
    lv_display_set_flush_cb(display, flush);
    assert(travel_ui_create());
    travel_state_t state;
    travel_state_init(&state);
    unsigned count = 0;
#ifdef TRAVEL_PREVIEW_INPUT
    assert(travel_state_apply(&state, &preview_snapshot));
    state.clock_valid = true;
    state.connected = true;
    unsigned tickets = state.snapshot.count ? (unsigned)state.snapshot.count : 1;
    for (unsigned ticket = 0; ticket < tickets; ++ticket) {
        state.selected = ticket;
        for (int details = 0; details < (state.snapshot.count ? 2 : 1); ++details) {
            state.details = details;
            travel_ui_update(&state, PREVIEW_NOW, 83, NULL);
            lv_tick_inc(100);
            lv_refr_now(display);
            inspect(lv_screen_active());
            save(argv[1], 0, (int)ticket, details);
            ++count;
        }
    }
#else
    for (int scenario = 0; scenario < TRAVEL_DEMO_SCENARIOS; ++scenario) {
        travel_demo_load(&state, (travel_demo_scenario_t)scenario, TRAVEL_DEMO_EPOCH);
        unsigned tickets = state.snapshot.count ? (unsigned)state.snapshot.count : 1;
        for (unsigned ticket = 0; ticket < tickets; ++ticket) {
            state.selected = ticket;
            for (int details = 0; details < (state.snapshot.count ? 2 : 1); ++details) {
                state.details = details;
                travel_ui_update(&state, TRAVEL_DEMO_EPOCH, 83, travel_demo_notice((travel_demo_scenario_t)scenario));
                lv_tick_inc(100);
                lv_refr_now(display);
                inspect(lv_screen_active());
                save(argv[1], scenario, (int)ticket, details);
                ++count;
            }
        }
    }
#endif
    assert(s_flushes >= count);
    puts("Native LVGL preview: PASS (all scenarios, active widget fonts and text bounds)");
    return 0;
}
