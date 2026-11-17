#include "travel_demo.h"

#include <string.h>

void travel_demo_load(travel_state_t *state, travel_demo_scenario_t scenario, int64_t now)
{
    /* 2026-11-18 07:25 UTC+8 = 1794957900, 2026-11-18 08:24 UTC+8 = 1794961440 */
    travel_snapshot_t snapshot = {
        .count = 1, .revision = 1, .updated_at = now, .expires_at = INT64_C(1794957900),
        .source = TRAVEL_SOURCE_LIVE,
        .trips = {
            { .id = "20261118-G7687-SHA-HGH", .service = "G7687", .origin = "上海虹桥",
              .destination = "杭州东", .gate = "19B", .seat = "05车 07D",
              .kind = TRAVEL_TRAIN, .status = TRAVEL_SCHEDULED,
              .planned_departure = INT64_C(1794957900),
              .estimated_departure = TRAVEL_UNKNOWN_TIME,
              .actual_departure = TRAVEL_UNKNOWN_TIME,
              .planned_arrival = INT64_C(1794961440) },
        }
    };
    if (snapshot.expires_at <= snapshot.updated_at) {
        snapshot.expires_at = snapshot.updated_at + 300;
    }
    if (scenario == TRAVEL_DEMO_EMPTY) {
        snapshot.count = 0;
    }
    size_t selected = state->selected;
    bool details = state->details;
    travel_state_init(state);
    (void)travel_state_apply(state, &snapshot);
    state->selected = selected < snapshot.count ? selected : 0;
    state->details = details && snapshot.count;
    state->clock_valid = true;
    state->connected = false;
}

const char *travel_demo_notice(travel_demo_scenario_t scenario)
{
    (void)scenario;
    return NULL;
}
