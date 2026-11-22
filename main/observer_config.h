#pragma once

#include <ctype.h>
#include <math.h>
#include <stdbool.h>
#include <stdlib.h>

/* Defaults belong to configuration only. The radar/ADS-B algorithms take
 * observer coordinates as parameters, and Settings + /api/config can edit them. */
#define OBSERVER_DEFAULT_LAT 10.7769
#define OBSERVER_DEFAULT_LON 106.7009
#define OBSERVER_DEFAULT_TZ "ICT-7"
#define OBSERVER_DEFAULT_UTC_OFFSET (7 * 3600)

static inline bool observer_location_valid(double lat, double lon)
{
    return isfinite(lat) && isfinite(lon) && lat >= -90 && lat <= 90 &&
           lon >= -180 && lon <= 180;
}

static inline bool observer_parse_coordinate(const char *text, double limit, double *out)
{
    if (text == NULL || *text == '\0') return false;
    char *end;
    double value = strtod(text, &end);
    if (end == text) return false;
    while (isspace((unsigned char)*end)) end++;
    if (*end || !isfinite(value) || value < -limit || value > limit) return false;
    *out = value;
    return true;
}
