/* Headless screenshot harness: boots the real UI with an optional recorded ADS-B
 * snapshot (empty traffic by default) and dumps PPM frames of each view at an arbitrary resolution.
 *
 *   simshot [--size WxH] [--views 0,1,2,3,4] [--out prefix]
 *
 * Renders <prefix>_view<N>.ppm per requested view. Used to verify the
 * 480x272 downscale and to prove 800x480 output stays untouched. */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <unistd.h>

#include "lvgl.h"
#include "app_port.h"
#include "sim_tick.h"

#include "airports.h"
#include "flight_model.h"
#include "logos.h"
#include "settings.h"
#include "tilemap.h"
#include "ui.h"
#include "ui_map.h"
#include "ui_settings.h"
#include "flight_data.h"
#include "observer_config.h"
#include "sdkconfig.h"
#include "flight_task.h"
#include "esp_timer.h"

#define CHECK(c) do { if (!(c)) { fprintf(stderr, "FAIL: %s (line %d)\n", #c, __LINE__); exit(1); } } while (0)

int sim_shot_ppm(const char *path);
void apk_paths_set_base(const char *dir);
void sim_pointer_set(int x, int y, bool pressed);

static void pump(int ms)
{
    for (int t = 0; t < ms; t += 5) {
        sim_tick_advance(5);
        lvgl_port_lock(-1);
        lv_timer_handler();
        lvgl_port_unlock();
    }
}

static unsigned widget_count(lv_obj_t *parent)
{
    unsigned count = 1;
    for (unsigned i = 0; i < lv_obj_get_child_cnt(parent); i++) {
        count += widget_count(lv_obj_get_child(parent, i));
    }
    return count;
}

static bool visible_text(lv_obj_t *parent, const char *text)
{
    if (!lv_obj_is_visible(parent)) return false;
    if (lv_obj_check_type(parent, &lv_label_class) && strcmp(lv_label_get_text(parent), text) == 0) return true;
    for (unsigned i = 0; i < lv_obj_get_child_cnt(parent); i++)
        if (visible_text(lv_obj_get_child(parent, i), text)) return true;
    return false;
}

static void touch_smoke(void)
{
    for (int view = 0; view < 5; view++) {
        sim_pointer_set(35 + view * 58, 78, true);
        pump(80);
        sim_pointer_set(35 + view * 58, 78, false);
        pump(80);
        /* Right panels are built in the documented view order after the
         * header/list. Assert the real pointer event shows exactly one. */
        for (int other = 0; other < 5; other++) {
            lv_obj_t *panel = lv_obj_get_child(lv_scr_act(), 2 + other);
            CHECK(lv_obj_has_flag(panel, LV_OBJ_FLAG_HIDDEN) == (other != view));
        }
    }
    puts("PASS: all five view tabs dispatched through LVGL pointer events");
}

static void tap_at(int x, int y)
{
    sim_pointer_set(x, y, true);
    pump(60);
    sim_pointer_set(x, y, false);
    pump(60);
}

static void tap_object(lv_obj_t *obj)
{
    lv_area_t bounds;
    lv_obj_get_coords(obj, &bounds);
    tap_at((bounds.x1 + bounds.x2) / 2, (bounds.y1 + bounds.y2) / 2);
}

static void tap_key(lv_obj_t *keyboard, const char *key)
{
    lv_btnmatrix_t *matrix = (lv_btnmatrix_t *)keyboard;
    lv_area_t bounds;
    lv_obj_get_coords(keyboard, &bounds);
    for (uint16_t i = 0; i < matrix->btn_cnt; i++) {
        if (strcmp(lv_btnmatrix_get_btn_text(keyboard, i), key) == 0) {
            lv_area_t button = matrix->button_areas[i];
            tap_at(bounds.x1 + (button.x1 + button.x2) / 2,
                   bounds.y1 + (button.y1 + button.y2) / 2);
            return;
        }
    }
    CHECK(false);
}

static void enter_coordinate(lv_obj_t *keyboard, lv_obj_t *field, const char *value)
{
    CHECK(lv_keyboard_get_textarea(keyboard) == field);
    CHECK(lv_keyboard_get_mode(keyboard) == LV_KEYBOARD_MODE_NUMBER);
    lv_textarea_set_cursor_pos(field, LV_TEXTAREA_CURSOR_LAST);
    size_t length = strlen(lv_textarea_get_text(field));
    for (size_t i = 0; i < length; i++) tap_key(keyboard, LV_SYMBOL_BACKSPACE);
    for (const char *p = value; *p; p++) tap_key(keyboard, (char[]){*p, 0});
    CHECK(strcmp(lv_textarea_get_text(field), value) == 0);
}

static lv_obj_t *find_widget(lv_obj_t *parent, const lv_obj_class_t *type)
{
    if (lv_obj_check_type(parent, type)) return parent;
    for (unsigned i = 0; i < lv_obj_get_child_cnt(parent); i++) {
        lv_obj_t *match = find_widget(lv_obj_get_child(parent, i), type);
        if (match != NULL) return match;
    }
    return NULL;
}

static void location_input_smoke(const char *prefix)
{
    settings_get()->use_fixed_loc = false;
    ui_settings_show_tab(0); /* Network is omitted in the host build. */
    pump(250);
    lv_obj_t *tabs = find_widget(lv_scr_act(), &lv_tabview_class);
    CHECK(tabs != NULL);
    lv_obj_t *page = lv_obj_get_child(lv_tabview_get_content(tabs), 0);
    lv_obj_t *fields[3] = {0};
    unsigned count = 0;
    lv_obj_t *automatic = NULL;
    for (unsigned i = 0; i < lv_obj_get_child_cnt(page) && count < 3; i++) {
        lv_obj_t *obj = lv_obj_get_child(page, i);
        if (lv_obj_check_type(obj, &lv_switch_class)) automatic = obj;
        if (lv_obj_check_type(obj, &lv_textarea_class)) fields[count++] = obj;
    }
    CHECK(count == 3 && automatic && lv_obj_has_state(automatic, LV_STATE_CHECKED));
    lv_obj_t *keyboard = find_widget(lv_layer_top(), &lv_keyboard_class);
    CHECK(keyboard != NULL);
    tap_object(fields[0]); /* City search opens a text keyboard. */
    CHECK(lv_keyboard_get_textarea(keyboard) == fields[0]);
    lv_area_t keys, longitude;
    lv_obj_get_coords(keyboard, &keys);
    lv_obj_get_coords(fields[2], &longitude);
    CHECK(keys.y1 > longitude.y2);

    tap_object(fields[1]); /* Latitude is reachable with City keyboard open. */
    CHECK(lv_obj_has_state(automatic, LV_STATE_CHECKED));
    enter_coordinate(keyboard, fields[1], "10.7238");
    CHECK(!lv_obj_has_state(automatic, LV_STATE_CHECKED));
    tap_key(keyboard, LV_SYMBOL_OK);
    CHECK(lv_obj_has_flag(keyboard, LV_OBJ_FLAG_HIDDEN));
    tap_object(fields[1]); /* Reopen the same field after OK. */
    CHECK(lv_keyboard_get_textarea(keyboard) == fields[1]);
    tap_object(fields[2]);
    enter_coordinate(keyboard, fields[2], "106.7090");
    char path[256];
    snprintf(path, sizeof(path), "%s_location-keyboard.ppm", prefix);
    CHECK(sim_shot_ppm(path) == 0);

    tap_at(646, 26); /* Settings → Save on the 800×480 layout. */
    CHECK(settings_get()->use_fixed_loc);
    CHECK(fabs(settings_get()->lat - 10.7238) < 0.00001);
    CHECK(fabs(settings_get()->lon - 106.7090) < 0.00001);
    puts("PASS: City to Latitude to Longitude through pointer events; coordinates visible, editable and applied on Save");
}

int main(int argc, char **argv)
{
    setenv("TZ", OBSERVER_DEFAULT_TZ, 1);

    int w = 800, h = 480;
    const char *prefix = "shot";
    const char *views = "0";
    const char *snapshot_path = NULL;
    bool smoke = false;
    int stress_cycles = 0;
    bool failure_smoke = false;
    bool location_smoke = false;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--size") == 0 && i + 1 < argc) {
            sscanf(argv[++i], "%dx%d", &w, &h);
        } else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
            prefix = argv[++i];
        } else if (strcmp(argv[i], "--views") == 0 && i + 1 < argc) {
            views = argv[++i];
        } else if (strcmp(argv[i], "--snapshot") == 0 && i + 1 < argc) {
            snapshot_path = argv[++i];
        } else if (strcmp(argv[i], "--touch-smoke") == 0) {
            smoke = true;
        } else if (strcmp(argv[i], "--stress") == 0 && i + 1 < argc) {
            stress_cycles = atoi(argv[++i]);
        } else if (strcmp(argv[i], "--fetch-failure-smoke") == 0) {
            failure_smoke = true;
        } else if (strcmp(argv[i], "--location-input-smoke") == 0) {
            location_smoke = true;
        }
    }

    apk_paths_set_base("../../assets-8mb");
    settings_load();
    /* Match the physical project's observer defaults for settings screenshots. */
    settings_get()->use_fixed_loc = true;
    settings_get()->lat = OBSERVER_DEFAULT_LAT;
    settings_get()->lon = OBSERVER_DEFAULT_LON;
    settings_get()->radius_nm = CONFIG_CANFLIGHT_RADIUS_NM;
    app_port_set_size(w, h);
    if (app_port_init("simshot") != 0) {
        return 1;
    }

    logos_init();
    airports_init();
    tilemap_init();
    ui_map_get_image();
    ui_map_get_image_small();

    aircraft_list_t list;
    memset(&list, 0, sizeof(list));
    if (snapshot_path != NULL) {
        FILE *f = fopen(snapshot_path, "rb");
        if (f == NULL) return 1;
        fseek(f, 0, SEEK_END);
        long size = ftell(f);
        rewind(f);
        char *json = calloc((size_t)size + 1, 1);
        if (json == NULL || fread(json, 1, size, f) != (size_t)size) return 1;
        fclose(f);
        settings_get()->hide_ground = false;
        if (flight_parse_snapshot(json, OBSERVER_DEFAULT_LAT, OBSERVER_DEFAULT_LON, &list) != ESP_OK) return 1;
        free(json);
    }

    lvgl_port_lock(-1);
    ui_init();
    ui_set_home(OBSERVER_DEFAULT_LAT, OBSERVER_DEFAULT_LON);
    char status[64];
    if (snapshot_path) snprintf(status, sizeof(status), "%d AC / OFFLINE SNAPSHOT", list.count);
    else strcpy(status, "NO AIRCRAFT DATA");
    ui_set_status(status);
    ui_update(&list);
    lvgl_port_unlock();

    pump(3000);

    if (smoke) {
        CHECK(w == 800 && h == 480);
        touch_smoke();
    }
    if (location_smoke) {
        CHECK(w == 800 && h == 480);
        location_input_smoke(prefix);
    }
    if (stress_cycles > 0) {
        aircraft_list_t empty = {0};
        for (int v = 0; v < 5; v++) { ui_set_view(v); pump(500); }
        unsigned before = widget_count(lv_scr_act());
        for (int i = 0; i < stress_cycles; i++) {
            lvgl_port_lock(-1);
            ui_update(i % 2 ? &list : &empty);
            ui_set_view(i % 5);
            lvgl_port_unlock();
            pump(80);
        }
        unsigned after = widget_count(lv_scr_act());
        CHECK(before == after);
        printf("PASS: %d redraw/data-clear cycles; widget count stable at %u\n", stress_cycles, after);
        ui_update(&list);
    }

    if (failure_smoke) {
        CHECK(list.count > 0 && visible_text(lv_scr_act(), list.ac[0].callsign));
        flight_task_start(); /* real worker, HTTP transport always fails in this harness */
        int64_t deadline = esp_timer_get_time() + 35LL * 1000000;
        bool stale_seen = false;
        while (esp_timer_get_time() < deadline) {
            pump(20);
            lvgl_port_lock(-1);
            stale_seen |= visible_text(lv_scr_act(), "DATA STALE / retrying");
            bool cleared = visible_text(lv_scr_act(), "NO AIRCRAFT DATA") &&
                           !visible_text(lv_scr_act(), list.ac[0].callsign);
            lvgl_port_unlock();
            if (cleared && stale_seen) break;
            usleep(20000);
        }
        CHECK(stale_seen && !visible_text(lv_scr_act(), list.ac[0].callsign));
        puts("PASS: real fetch worker + failed HTTP -> STALE -> NO AIRCRAFT DATA; old targets hidden");
    }

    char path[256];
    for (const char *v = views; *v != '\0'; v++) {
        if (*v == 's') {   /* settings screen, tabs s0..s3 via next digit */
            int tab = (v[1] >= '0' && v[1] <= '9') ? *++v - '0' : 0;
            lvgl_port_lock(-1);
            ui_settings_open();
            ui_settings_show_tab(tab);
            lvgl_port_unlock();
            pump(2000);
            snprintf(path, sizeof(path), "%s_settings%d.ppm", prefix, tab);
            if (sim_shot_ppm(path) != 0) {
                return 1;
            }
            printf("wrote %s\n", path);
            continue;
        }
        if (*v < '0' || *v > '9') {
            continue;
        }
        lvgl_port_lock(-1);
        ui_set_view(*v - '0');
        lvgl_port_unlock();
        pump(2000);
        snprintf(path, sizeof(path), "%s_view%c.ppm", prefix, *v);
        if (sim_shot_ppm(path) != 0) {
            fprintf(stderr, "shot failed: %s\n", path);
            return 1;
        }
        printf("wrote %s\n", path);
    }
    return 0;
}
