#pragma once

#include "travel_state.h"
#include <stdbool.h>

/* Caller holds bsp_lvgl_lock(). This screen and its fonts have app lifetime. */
bool travel_ui_create(void);
void travel_ui_update(const travel_state_t *state, int64_t now, int battery_soc,
                      const char *notice);
