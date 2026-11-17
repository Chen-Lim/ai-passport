#include "travel_ui.h"

#include "bsp_pins.h"
#include "lvgl.h"
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

LV_FONT_DECLARE(travel_font_18);

#define INK 0x17212B
#define PAPER 0xF4F0E8
#define MUTED 0x697580
#define BACKGROUND 0x101923
#define ORANGE 0xD98035
#define TEAL 0x207D76

static lv_obj_t *s_screen;
static lv_obj_t *s_card;
static lv_obj_t *s_battery;
static lv_obj_t *s_source;
static lv_obj_t *s_heading;
static lv_obj_t *s_service;
static lv_obj_t *s_route;
static lv_obj_t *s_status;
static lv_obj_t *s_time;
static lv_obj_t *s_time_caption;
static lv_obj_t *s_gate;
static lv_obj_t *s_bottom;
static lv_obj_t *s_update;
static lv_obj_t *s_hint;
static lv_obj_t *s_detail;

static lv_obj_t *label(lv_obj_t *parent, int x, int y, int width,
                       const lv_font_t *font, uint32_t color)
{
    lv_obj_t *object = lv_label_create(parent);
    lv_obj_set_pos(object, x, y);
    lv_obj_set_width(object, width);
    lv_obj_set_style_text_font(object, font, LV_PART_MAIN);
    lv_obj_set_style_text_color(object, lv_color_hex(color), LV_PART_MAIN);
    lv_label_set_long_mode(object, LV_LABEL_LONG_CLIP);
    return object;
}

static bool font_supports(const lv_font_t *font, const char *text)
{
    const unsigned char *p = (const unsigned char *)text;
    while (*p) {
        uint32_t cp = *p++;
        if (cp >= 0x80) {
            unsigned count = cp < 0xe0 ? 1 : (cp < 0xf0 ? 2 : 3);
            cp &= count == 1 ? 0x1f : (count == 2 ? 0x0f : 0x07);
            while (count--) cp = (cp << 6) | (*p++ & 0x3f);
        }
        if (cp == '\n') continue;
        lv_font_glyph_dsc_t glyph = {0};
        if (!lv_font_get_glyph_dsc(font, &glyph, cp, 0) || glyph.is_placeholder) return false;
    }
    return true;
}

/* Check the font actually selected by this widget, including dynamic names. */
static void text(lv_obj_t *object, const char *value)
{
    const lv_font_t *font = lv_obj_get_style_text_font(object, LV_PART_MAIN);
    if (font_supports(font, value)) {
        if (strcmp(lv_label_get_text(object), value) != 0) lv_label_set_text(object, value);
    } else {
        lv_obj_set_style_text_font(object, &travel_font_18, LV_PART_MAIN);
        if (strcmp(lv_label_get_text(object), "文字不支持") != 0) lv_label_set_text(object, "文字不支持");
    }
}

static const char *status_name(travel_status_t status)
{
    switch (status) {
    case TRAVEL_SCHEDULED: return "按计划";
    case TRAVEL_BOARDING: return "正在登乘";
    case TRAVEL_DELAYED: return "已延误";
    case TRAVEL_DEPARTED: return "已出发";
    case TRAVEL_ARRIVED: return "已到达";
    case TRAVEL_CANCELLED: return "已取消";
    default: return "状态未知";
    }
}

bool travel_ui_create(void)
{
    if (s_screen) return true;
    /* Positive and negative checks catch a missing font or placeholder-only setup. */
    if (!font_supports(&travel_font_18, "行程模拟数据文字不支持") ||
        font_supports(&travel_font_18, "\u9f98")) return false; /* glyph-check: ignore: negative probe */

    s_screen = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(s_screen, lv_color_hex(BACKGROUND), 0);
    lv_obj_remove_flag(s_screen, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_t *title = label(s_screen, 24, 12, 115, &travel_font_18, PAPER);
    text(title, "出行口袋");
    s_battery = label(s_screen, BSP_LCD_W - 77, 14, 52, &lv_font_montserrat_14, PAPER);
    lv_obj_set_style_text_align(s_battery, LV_TEXT_ALIGN_RIGHT, 0);
    s_source = label(s_screen, 24, 35, BSP_LCD_W - 48, &travel_font_18, 0xDFAC71);

    s_card = lv_obj_create(s_screen);
    lv_obj_set_pos(s_card, 12, 61);
    lv_obj_set_size(s_card, BSP_LCD_W - 24, 207);
    lv_obj_set_style_bg_color(s_card, lv_color_hex(PAPER), 0);
    lv_obj_set_style_radius(s_card, 12, 0);
    lv_obj_set_style_border_width(s_card, 0, 0);
    lv_obj_set_style_pad_all(s_card, 0, 0);
    lv_obj_remove_flag(s_card, LV_OBJ_FLAG_SCROLLABLE);
    s_heading = label(s_card, 12, 9, 192, &travel_font_18, TEAL);
    s_service = label(s_card, 12, 33, 192, &lv_font_montserrat_32, INK);
    s_route = label(s_card, 12, 76, 192, &travel_font_18, INK);
    s_status = label(s_card, 12, 102, 192, &travel_font_18, TEAL);
    s_time_caption = label(s_card, 12, 128, 95, &travel_font_18, MUTED);
    s_time = label(s_card, 114, 129, 91, &lv_font_montserrat_20, INK);
    lv_obj_set_style_text_align(s_time, LV_TEXT_ALIGN_RIGHT, 0);
    s_gate = label(s_card, 12, 155, 192, &travel_font_18, INK);
    s_bottom = label(s_card, 12, 181, 192, &travel_font_18, MUTED);
    s_detail = label(s_card, 12, 76, 192, &travel_font_18, INK);
    lv_obj_add_flag(s_detail, LV_OBJ_FLAG_HIDDEN);
    s_update = label(s_screen, 24, 273, BSP_LCD_W - 48, &travel_font_18, 0xB0B9C1);
    s_hint = label(s_screen, 24, BSP_LCD_H - 25, BSP_LCD_W - 48, &travel_font_18, PAPER);
    lv_screen_load(s_screen);
    return true;
}

void travel_ui_update(const travel_state_t *state, int64_t now, int battery_soc,
                      const char *notice)
{
    if (!s_screen) return;
    char buffer[256];
    snprintf(buffer, sizeof(buffer), battery_soc < 0 ? "--%%" : "%d%%", battery_soc);
    text(s_battery, buffer);
    bool demo = state->has_snapshot && state->snapshot.source == TRAVEL_SOURCE_DEMO;
    text(s_source, demo ? "模拟数据 / 非实时" : "行程数据 / 待核对");
    travel_freshness_t freshness = travel_state_freshness(state, now);
    if (!state->has_snapshot || !state->snapshot.count) {
        text(s_heading, "行程卡片");
        text(s_service, "--");
        text(s_route, "暂无行程");
        text(s_status, state->connected ? "等待同步" : "尚未连接");
        text(s_time_caption, "出发时间");
        text(s_time, "--:--");
        text(s_gate, "请先添加行程");
        text(s_bottom, "数据未就绪");
    } else {
        const travel_trip_t *trip = &state->snapshot.trips[state->selected];
        uint32_t accent = trip->kind == TRAVEL_TRAIN ? TEAL : ORANGE;
        if (trip->status == TRAVEL_CANCELLED || trip->status == TRAVEL_DELAYED) accent = 0xB64E36;
        lv_obj_set_style_text_color(s_heading, lv_color_hex(accent), 0);
        lv_obj_set_style_text_color(s_status, lv_color_hex(accent), 0);
        char date[16];
        travel_format_date(trip->planned_departure, 480, date, sizeof(date));
        snprintf(buffer, sizeof(buffer), "%s  %s  %u/%u", trip->kind == TRAVEL_TRAIN ? "火车" : "飞机", date + 5,
                 (unsigned)state->selected + 1, (unsigned)state->snapshot.count);
        text(s_heading, buffer);
        lv_obj_set_style_text_font(s_service, &lv_font_montserrat_32, LV_PART_MAIN);
        text(s_service, trip->service);
        snprintf(buffer, sizeof(buffer), "%s > %s", trip->origin, trip->destination);
        text(s_route, buffer);
        text(s_status, status_name(trip->status));
        char planned[8], estimated[8], arrival[8], actual[8];
        travel_format_time(trip->planned_departure, 480, planned, sizeof(planned));
        travel_format_time(trip->estimated_departure, 480, estimated, sizeof(estimated));
        travel_format_time(trip->actual_departure, 480, actual, sizeof(actual));
        travel_format_time(trip->planned_arrival, 480, arrival, sizeof(arrival));
        text(s_time_caption, trip->estimated_departure >= 0 ? "预计出发" : "计划出发");
        text(s_time, trip->estimated_departure >= 0 ? estimated : planned);
        snprintf(buffer, sizeof(buffer), "%s %s", trip->kind == TRAVEL_TRAIN ? "检票口" : "登机口",
                 trip->gate[0] ? trip->gate : "暂无信息");
        text(s_gate, buffer);
        int64_t minutes;
        if (freshness == TRAVEL_FRESH && travel_minutes_until(trip, now, &minutes)) {
            snprintf(buffer, sizeof(buffer), "距出发 %" PRId64 " 分钟", minutes);
        } else {
            snprintf(buffer, sizeof(buffer), "%s", freshness == TRAVEL_STALE ? "请更新行程状态" : "以车站机场信息为准");
        }
        text(s_bottom, buffer);
        snprintf(buffer, sizeof(buffer), "%s UTC+8\n计划 %s\n预计 %s\n实际 %s\n到达 %s\n座位 %s",
                 date, planned, estimated, actual, arrival, trip->seat[0] ? trip->seat : "暂无信息");
        text(s_detail, buffer);
    }
    lv_obj_t *summary[] = {s_route, s_status, s_time_caption, s_time, s_gate, s_bottom};
    bool show_details = state->details && state->snapshot.count;
    for (size_t i = 0; i < sizeof(summary) / sizeof(summary[0]); ++i) {
        if (show_details) lv_obj_add_flag(summary[i], LV_OBJ_FLAG_HIDDEN);
        else lv_obj_remove_flag(summary[i], LV_OBJ_FLAG_HIDDEN);
    }
    if (show_details) lv_obj_remove_flag(s_detail, LV_OBJ_FLAG_HIDDEN);
    else lv_obj_add_flag(s_detail, LV_OBJ_FLAG_HIDDEN);

    if (notice && *notice) {
        text(s_update, notice);
    } else if (freshness == TRAVEL_CLOCK_UNSET) {
        text(s_update, "时间未同步");
    } else if (freshness == TRAVEL_STALE) {
        text(s_update, "数据已过期");
    } else if (!state->has_snapshot) {
        text(s_update, "等待行程数据");
    } else {
        char updated[8];
        travel_format_time(state->snapshot.updated_at, 480, updated, sizeof(updated));
        snprintf(buffer, sizeof(buffer), "%s %s", demo ? "模拟更新" : "更新", updated);
        text(s_update, buffer);
    }
    text(s_hint, show_details ? "长按确定返回" : "上下切换 确定详情");
}
