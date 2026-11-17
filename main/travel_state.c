#include "travel_state.h"

#include <stdio.h>
#include <string.h>

/* Supported calendar range is 1970..2099; bound arithmetic before formatting. */
#define MAX_TIMESTAMP INT64_C(4102444799)

static bool time_valid(int64_t value)
{
    return value == TRAVEL_UNKNOWN_TIME || (value >= 0 && value <= MAX_TIMESTAMP);
}

bool travel_utf8_valid(const char *text, size_t capacity)
{
    if (!text) return false;
    size_t i = 0;
    while (i < capacity && text[i]) {
        uint32_t cp = (unsigned char)text[i++];
        if (cp < 0x80) {
            if (cp < 0x20 || cp == 0x7f) return false;
            continue;
        }
        unsigned trailing;
        uint32_t minimum;
        if (cp >= 0xc2 && cp <= 0xdf) {
            trailing = 1; minimum = 0x80; cp &= 0x1f;
        } else if (cp >= 0xe0 && cp <= 0xef) {
            trailing = 2; minimum = 0x800; cp &= 0x0f;
        } else if (cp >= 0xf0 && cp <= 0xf4) {
            trailing = 3; minimum = 0x10000; cp &= 0x07;
        } else {
            return false;
        }
        while (trailing--) {
            if (i >= capacity) return false;
            unsigned char next = (unsigned char)text[i++];
            if ((next & 0xc0) != 0x80) return false;
            cp = (cp << 6) | (next & 0x3f);
        }
        if (cp < minimum || cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff)) return false;
    }
    return i < capacity;
}

void travel_state_init(travel_state_t *state)
{
    memset(state, 0, sizeof(*state));
}

bool travel_snapshot_valid(const travel_snapshot_t *s)
{
    if (!s || s->count > TRAVEL_MAX_TRIPS || s->source > TRAVEL_SOURCE_LIVE ||
        s->source < TRAVEL_SOURCE_DEMO || s->updated_at < 0 ||
        s->expires_at <= s->updated_at || !time_valid(s->expires_at)) return false;
    for (size_t i = 0; i < s->count; ++i) {
        const travel_trip_t *t = &s->trips[i];
        if (!t->id[0] || !t->service[0] || !t->origin[0] || !t->destination[0] ||
            !travel_utf8_valid(t->id, sizeof(t->id)) ||
            !travel_utf8_valid(t->service, sizeof(t->service)) ||
            !travel_utf8_valid(t->origin, sizeof(t->origin)) ||
            !travel_utf8_valid(t->destination, sizeof(t->destination)) ||
            !travel_utf8_valid(t->gate, sizeof(t->gate)) ||
            !travel_utf8_valid(t->seat, sizeof(t->seat)) ||
            t->kind < TRAVEL_TRAIN || t->kind > TRAVEL_FLIGHT ||
            t->status < TRAVEL_SCHEDULED || t->status > TRAVEL_UNKNOWN ||
            !time_valid(t->planned_departure) || !time_valid(t->estimated_departure) ||
            !time_valid(t->actual_departure) || !time_valid(t->planned_arrival)) return false;
        for (size_t j = 0; j < i; ++j) {
            if (strcmp(t->id, s->trips[j].id) == 0) return false;
        }
    }
    return true;
}

bool travel_state_apply(travel_state_t *state, const travel_snapshot_t *snapshot)
{
    if (!travel_snapshot_valid(snapshot)) return false;
    if (state->has_snapshot &&
        (snapshot->source != state->snapshot.source ||
         snapshot->updated_at < state->snapshot.updated_at ||
         snapshot->revision <= state->snapshot.revision)) return false;
    char selected_id[sizeof(snapshot->trips[0].id)] = {0};
    if (state->has_snapshot && state->selected < state->snapshot.count) {
        memcpy(selected_id, state->snapshot.trips[state->selected].id, sizeof(selected_id));
    }
    state->snapshot = *snapshot;
    state->has_snapshot = true;
    state->selected = 0;
    for (size_t i = 0; i < snapshot->count; ++i) {
        if (strcmp(selected_id, snapshot->trips[i].id) == 0) state->selected = i;
    }
    if (!snapshot->count) state->details = false;
    return true;
}

void travel_state_select(travel_state_t *state, int direction)
{
    size_t count = state->snapshot.count;
    if (!count) return;
    if (direction > 0) state->selected = (state->selected + 1) % count;
    if (direction < 0) state->selected = (state->selected + count - 1) % count;
}

bool travel_state_action(travel_state_t *state, travel_action_t action, bool wake_only)
{
    if (wake_only) return false;
    switch (action) {
    case TRAVEL_PREVIOUS: travel_state_select(state, -1); break;
    case TRAVEL_NEXT: travel_state_select(state, 1); break;
    case TRAVEL_CONFIRM:
        if (state->snapshot.count) state->details = !state->details;
        break;
    case TRAVEL_BACK:
        if (!state->details) return true;
        state->details = false;
        break;
    }
    return false;
}

unsigned travel_idle_backlight(int64_t idle_us)
{
    if (idle_us >= INT64_C(60000000)) return 0;
    if (idle_us >= INT64_C(30000000)) return 8;
    return 65;
}

travel_freshness_t travel_state_freshness(const travel_state_t *state, int64_t now)
{
    if (!state->has_snapshot) return TRAVEL_EMPTY;
    if (!state->clock_valid || now < 0 || now > MAX_TIMESTAMP) return TRAVEL_CLOCK_UNSET;
    if (now < state->snapshot.updated_at || now >= state->snapshot.expires_at) return TRAVEL_STALE;
    return TRAVEL_FRESH;
}

bool travel_minutes_until(const travel_trip_t *trip, int64_t now, int64_t *minutes)
{
    if (!trip || !minutes || now < 0 || now > MAX_TIMESTAMP ||
        trip->status == TRAVEL_CANCELLED || trip->status == TRAVEL_UNKNOWN ||
        trip->status == TRAVEL_DEPARTED || trip->status == TRAVEL_ARRIVED) return false;
    int64_t target = trip->estimated_departure != TRAVEL_UNKNOWN_TIME
                   ? trip->estimated_departure : trip->planned_departure;
    if (target < now || !time_valid(target)) return false;
    *minutes = (target - now + 59) / 60;
    return true;
}

void travel_format_time(int64_t utc, int offset_minutes, char *out, size_t capacity)
{
    if (!out || !capacity) return;
    if (utc < 0 || utc > MAX_TIMESTAMP || offset_minutes < -720 || offset_minutes > 840) {
        snprintf(out, capacity, "--:--");
        return;
    }
    int64_t local = (utc + offset_minutes * INT64_C(60)) % INT64_C(86400);
    if (local < 0) local += INT64_C(86400);
    snprintf(out, capacity, "%02d:%02d", (int)(local / 3600), (int)((local / 60) % 60));
}

void travel_format_date(int64_t utc, int offset_minutes, char *out, size_t capacity)
{
    if (!out || !capacity) return;
    if (utc < 0 || utc > MAX_TIMESTAMP || offset_minutes < -720 || offset_minutes > 840) {
        snprintf(out, capacity, "---- -- --");
        return;
    }
    int64_t local = utc + offset_minutes * INT64_C(60);
    int64_t days = local / 86400;
    if (local < 0 && local % 86400) --days;
    /* Gregorian civil date, independent of libc timezone and process environment. */
    int64_t z = days + 719468;
    int64_t era = z / 146097;
    unsigned doe = (unsigned)(z - era * 146097);
    unsigned yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    int year = (int)(yoe + era * 400);
    unsigned doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    unsigned mp = (5 * doy + 2) / 153;
    unsigned day = doy - (153 * mp + 2) / 5 + 1;
    int month = (int)mp + (mp < 10 ? 3 : -9);
    year += month <= 2;
    snprintf(out, capacity, "%04d-%02d-%02u", year, month, day);
}
