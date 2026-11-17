#include "travel_state.h"
#include "travel_demo.h"

#include <assert.h>
#include <stdio.h>
#include <string.h>

static travel_snapshot_t snapshot(void)
{
    travel_snapshot_t s = {
        .count = 2, .revision = 1, .updated_at = 1000, .expires_at = 1300,
        .source = TRAVEL_SOURCE_DEMO,
        .trips = {
            { .id = "train-date-route", .service = "G12", .origin = "Shanghai",
              .destination = "Beijing", .kind = TRAVEL_TRAIN, .status = TRAVEL_SCHEDULED,
              .planned_departure = 2000, .estimated_departure = -1,
              .actual_departure = -1, .planned_arrival = 9000 },
            { .id = "flight-date-route", .service = "MU123", .origin = "PVG",
              .destination = "PEK", .kind = TRAVEL_FLIGHT, .status = TRAVEL_DELAYED,
              .planned_departure = 2000, .estimated_departure = 2900,
              .actual_departure = -1, .planned_arrival = 9000 },
        }
    };
    return s;
}

int main(void)
{
    travel_state_t state;
    travel_state_init(&state);
    assert(travel_state_freshness(&state, 1000) == TRAVEL_EMPTY);
    travel_state_select(&state, -1);
    assert(state.selected == 0);
    travel_snapshot_t s = snapshot();
    assert(travel_state_apply(&state, &s));
    assert(travel_state_freshness(&state, 1100) == TRAVEL_CLOCK_UNSET);
    state.clock_valid = true;
    state.connected = false;
    assert(travel_state_freshness(&state, 1100) == TRAVEL_FRESH);
    assert(travel_state_freshness(&state, 1300) == TRAVEL_STALE);
    assert(travel_state_freshness(&state, 999) == TRAVEL_STALE);
    assert(!travel_state_action(&state, TRAVEL_CONFIRM, true));
    assert(!state.details); /* first dark-screen action only wakes */
    assert(!travel_state_action(&state, TRAVEL_CONFIRM, false));
    assert(state.details);
    assert(!travel_state_action(&state, TRAVEL_BACK, false));
    assert(!state.details);
    assert(travel_state_action(&state, TRAVEL_BACK, false));
    assert(!travel_state_action(&state, TRAVEL_BACK, true));
    assert(travel_idle_backlight(29999999) == 65);
    assert(travel_idle_backlight(30000000) == 8);
    assert(travel_idle_backlight(59999999) == 8);
    assert(travel_idle_backlight(60000000) == 0);
    travel_state_select(&state, -1);
    assert(state.selected == 1);
    travel_state_select(&state, 1);
    assert(state.selected == 0);
    assert(!travel_state_apply(&state, &s));
    s.revision++;
    strcpy(s.trips[0].id, s.trips[1].id);
    assert(!travel_state_apply(&state, &s));
    assert(strcmp(state.snapshot.trips[0].id, "train-date-route") == 0);
    s = snapshot(); s.revision++;
    travel_state_select(&state, 1);
    travel_trip_t tmp = s.trips[0]; s.trips[0] = s.trips[1]; s.trips[1] = tmp;
    assert(travel_state_apply(&state, &s));
    assert(state.selected == 0); /* selection follows ID after server reordering */
    s.revision++;
    s.updated_at = 999;
    assert(!travel_state_apply(&state, &s));
    s = snapshot(); s.revision = 3; s.source = TRAVEL_SOURCE_LIVE;
    assert(!travel_state_apply(&state, &s)); /* source changes must explicitly reset */

    int64_t minutes = -1;
    travel_trip_t t = snapshot().trips[0];
    assert(travel_minutes_until(&t, 1939, &minutes) && minutes == 2);
    assert(travel_minutes_until(&t, 2000, &minutes) && minutes == 0);
    assert(!travel_minutes_until(&t, 2001, &minutes));
    assert(t.status == TRAVEL_SCHEDULED); /* clock never fabricates departure */
    t.estimated_departure = 2900;
    assert(travel_minutes_until(&t, 2000, &minutes) && minutes == 15);
    for (int status = TRAVEL_DEPARTED; status <= TRAVEL_UNKNOWN; ++status) {
        t.status = (travel_status_t)status;
        assert(!travel_minutes_until(&t, 1000, &minutes));
    }
    t.status = TRAVEL_SCHEDULED; t.planned_departure = -1; t.estimated_departure = -1;
    assert(!travel_minutes_until(&t, 1000, &minutes));

    char text[8];
    travel_format_time(86340, 480, text, sizeof(text));
    assert(strcmp(text, "07:59") == 0); /* next local day */
    travel_format_time(0, -60, text, sizeof(text));
    assert(strcmp(text, "23:00") == 0);
    travel_format_time(-1, 480, text, sizeof(text));
    assert(strcmp(text, "--:--") == 0);
    char date[16];
    travel_format_date(TRAVEL_DEMO_EPOCH, 480, date, sizeof(date));
    assert(strcmp(date, "2026-11-17") == 0);
    travel_format_date(1709164800, 0, date, sizeof(date));
    assert(strcmp(date, "2024-02-29") == 0);
    travel_format_date(0, -60, date, sizeof(date));
    assert(strcmp(date, "1969-12-31") == 0);
    assert(travel_utf8_valid("\xe4\xb8\xad", 4));
    assert(!travel_utf8_valid("\xe4\xb8", 3));
    assert(!travel_utf8_valid("\xc0\xaf", 3));
    assert(!travel_utf8_valid("\xed\xa0\x80", 4));
    assert(!travel_utf8_valid("a\nb", 4));
    assert(!travel_utf8_valid("abcd", 4));
    s = snapshot();
    memset(s.trips[0].origin, 'a', sizeof(s.trips[0].origin));
    assert(!travel_snapshot_valid(&s));
    s = snapshot(); s.count = TRAVEL_MAX_TRIPS + 1;
    assert(!travel_snapshot_valid(&s));
    s = snapshot(); s.expires_at = s.updated_at;
    assert(!travel_snapshot_valid(&s));
    s = snapshot(); s.count = 0; s.revision = 3;
    assert(travel_state_apply(&state, &s));
    assert(state.selected == 0 && !state.details);
    for (int scenario = 0; scenario < TRAVEL_DEMO_SCENARIOS; ++scenario) {
        travel_demo_load(&state, (travel_demo_scenario_t)scenario, TRAVEL_DEMO_EPOCH);
        assert(state.has_snapshot && state.snapshot.source == TRAVEL_SOURCE_LIVE);
        assert(state.clock_valid);
        assert(travel_snapshot_valid(&state.snapshot));
        if (scenario == TRAVEL_DEMO_NORMAL) {
            assert(state.snapshot.count == 1);
            assert(strcmp(state.snapshot.trips[0].service, "G7687") == 0);
            assert(strcmp(state.snapshot.trips[0].origin, "上海虹桥") == 0);
            assert(strcmp(state.snapshot.trips[0].destination, "杭州东") == 0);
            assert(strcmp(state.snapshot.trips[0].gate, "19B") == 0);
            assert(strcmp(state.snapshot.trips[0].seat, "05车 07D") == 0);
        }
        if (scenario == TRAVEL_DEMO_EMPTY) assert(state.snapshot.count == 0);
    }
    puts("Travel state: PASS (freshness, ordering, countdown, UTC offset, bounded UTF-8)");
    return 0;
}
