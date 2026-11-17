#pragma once

#include "travel_state.h"

typedef enum {
    TRAVEL_DEMO_NORMAL, TRAVEL_DEMO_EMPTY, TRAVEL_DEMO_SCENARIOS
} travel_demo_scenario_t;

/* Fixed reference epoch (2026-11-17 08:00 UTC+8) used by host tests. */
#define TRAVEL_DEMO_EPOCH INT64_C(1794873600)

void travel_demo_load(travel_state_t *state, travel_demo_scenario_t scenario, int64_t now);
const char *travel_demo_notice(travel_demo_scenario_t scenario);
