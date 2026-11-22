/* Offline regression tests link the production parser/geo math. No radio IO. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "flight_data.h"
#include "geo_math.h"
#include "settings.h"
#include "observer_config.h"
#include "waveshare7_verified.h"

static settings_t config;
settings_t *settings_get(void) { return &config; }
int64_t esp_timer_get_time(void) { return 1000000; }

int main(int argc, char **argv)
{
    assert(argc == 2);
    config.show_classes = FCLS_ALL_MASK;
    aircraft_list_t *list = calloc(1, sizeof(*list));
    assert(list);
    assert(flight_parse_snapshot("{\"ac\":[]}", 10, 106, list) == ESP_OK && list->count == 0);
    assert(flight_parse_snapshot("{}", 10, 106, list) == ESP_ERR_INVALID_RESPONSE);
    assert(flight_parse_snapshot("{", 10, 106, list) == ESP_ERR_INVALID_RESPONSE);
    assert(flight_parse_snapshot("{\"ac\":[]}", NAN, 106, list) == ESP_ERR_INVALID_ARG);
    assert(flight_parse_snapshot("{\"ac\":[{\"hex\":\"bad001\",\"lat\":999,\"lon\":106.7},"
                                 "{\"hex\":\"bad002\",\"lat\":10.7}]}", 10, 106, list) == ESP_OK);
    assert(list->count == 0);

    FILE *f = fopen(argv[1], "rb");
    assert(f);
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    rewind(f);
    char *json = calloc((size_t)size + 1, 1);
    assert(json && fread(json, 1, size, f) == (size_t)size);
    fclose(f);
    assert(flight_parse_snapshot(json, OBSERVER_DEFAULT_LAT, OBSERVER_DEFAULT_LON, list) == ESP_OK);
    assert(list->count > 0 && list->count <= MAX_AIRCRAFT);
    for (int i = 0; i < list->count; i++) {
        const aircraft_t *a = &list->ac[i];
        assert(a->has_pos && observer_location_valid(a->lat, a->lon));
        assert(isfinite(a->dist_nm) && a->dist_nm >= 0);
        if (i) assert(a->dist_nm >= list->ac[i - 1].dist_nm);
    }
    printf("real ADS-B snapshot: %d aircraft parsed/sorted; no synthetic traffic\n", list->count);
    free(json);
    free(list);

    double coordinate = 123;
    assert(observer_parse_coordinate(" 10.7769 ", 90, &coordinate) && fabs(coordinate-10.7769) < 1e-9);
    assert(!observer_parse_coordinate("nan", 90, &coordinate));
    assert(!observer_parse_coordinate("inf", 90, &coordinate));
    assert(!observer_parse_coordinate("106.7oops", 180, &coordinate));
    assert(!observer_parse_coordinate("91", 90, &coordinate));
    assert(!observer_parse_coordinate("", 90, &coordinate));
    assert(observer_location_valid(0, 0));
    assert(!observer_location_valid(90.1, 0));
    assert(w7_output_mask(0, 0) == 0x40);
    assert(w7_output_mask(0, 1) == 0x42);
    assert(w7_output_mask(1, 0) == 0x44);
    assert(w7_output_mask(1, 1) == 0x46);
    assert(fabs(geo_haversine_km(10.7769, 106.7009, 10.7769, 106.7009)) < 1e-9);
    double lat, lon;
    geo_gc_point(10, 106, 20, 110, 0, &lat, &lon);
    assert(fabs(lat-10) < 1e-9 && fabs(lon-106) < 1e-9);
    puts("PASS: empty/malformed/no-position/out-of-range data, observer config, CH422G masks, geo math");
    return 0;
}
