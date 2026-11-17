#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define TRAVEL_MAX_TRIPS 4
#define TRAVEL_UNKNOWN_TIME INT64_C(-1)

typedef enum { TRAVEL_TRAIN, TRAVEL_FLIGHT } travel_kind_t;
typedef enum {
    TRAVEL_SCHEDULED, TRAVEL_BOARDING, TRAVEL_DELAYED,
    TRAVEL_DEPARTED, TRAVEL_ARRIVED, TRAVEL_CANCELLED, TRAVEL_UNKNOWN
} travel_status_t;
typedef enum { TRAVEL_SOURCE_DEMO, TRAVEL_SOURCE_LIVE } travel_source_t;
typedef enum { TRAVEL_EMPTY, TRAVEL_FRESH, TRAVEL_STALE, TRAVEL_CLOCK_UNSET } travel_freshness_t;
typedef enum { TRAVEL_PREVIOUS, TRAVEL_NEXT, TRAVEL_CONFIRM, TRAVEL_BACK } travel_action_t;

/* UTC Unix seconds; -1 represents an unavailable time, never an inferred event. */
typedef struct {
    char id[24];
    char service[16];
    char origin[40];
    char destination[40];
    char gate[24];
    char seat[24];
    travel_kind_t kind;
    travel_status_t status;
    int64_t planned_departure;
    int64_t estimated_departure;
    int64_t actual_departure;
    int64_t planned_arrival;
} travel_trip_t;

typedef struct {
    travel_trip_t trips[TRAVEL_MAX_TRIPS];
    size_t count;
    uint32_t revision;
    int64_t updated_at;
    int64_t expires_at;
    travel_source_t source;
} travel_snapshot_t;

typedef struct {
    travel_snapshot_t snapshot;
    size_t selected;
    bool details;
    bool connected;
    bool clock_valid;
    bool has_snapshot;
} travel_state_t;

void travel_state_init(travel_state_t *state);
bool travel_snapshot_valid(const travel_snapshot_t *snapshot);
/* Invalid or older snapshots never destroy the previous usable state. */
bool travel_state_apply(travel_state_t *state, const travel_snapshot_t *snapshot);
void travel_state_select(travel_state_t *state, int direction);
/* Returns true when BACK at home requests the next demo scenario. */
bool travel_state_action(travel_state_t *state, travel_action_t action, bool wake_only);
unsigned travel_idle_backlight(int64_t idle_us);
travel_freshness_t travel_state_freshness(const travel_state_t *state, int64_t now);
bool travel_minutes_until(const travel_trip_t *trip, int64_t now, int64_t *minutes);
void travel_format_time(int64_t utc, int offset_minutes, char *out, size_t capacity);
void travel_format_date(int64_t utc, int offset_minutes, char *out, size_t capacity);
bool travel_utf8_valid(const char *text, size_t capacity);
