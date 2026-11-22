#include "geolocate.h"

#include <stdlib.h>
#include <string.h>
#include "cJSON.h"
#include "esp_log.h"
#include "http_util.h"
#include "settings.h"
#include "observer_config.h"

static const char *TAG = "geoloc";

esp_err_t geolocate_get(double *lat, double *lon, char *city, size_t city_len)
{
    if (city != NULL && city_len > 0) {
        city[0] = '\0';
    }

    const settings_t *cfg = settings_get();
    if (cfg->use_fixed_loc) {
        bool valid = observer_location_valid(cfg->lat, cfg->lon);
        *lat = valid ? cfg->lat : OBSERVER_DEFAULT_LAT;
        *lon = valid ? cfg->lon : OBSERVER_DEFAULT_LON;
        ESP_LOGI(TAG, "using fixed location %.4f, %.4f", *lat, *lon);
        return ESP_OK;
    }

    char *buf = malloc(2048);
    if (buf == NULL) {
        return ESP_ERR_NO_MEM;
    }

    esp_err_t err = http_get_to_buffer("http://ip-api.com/json/", buf, 2048, NULL);
    if (err != ESP_OK) {
        free(buf);
        return err;
    }

    cJSON *root = cJSON_Parse(buf);
    free(buf);
    if (root == NULL) {
        return ESP_ERR_INVALID_RESPONSE;
    }

    cJSON *jlat = cJSON_GetObjectItem(root, "lat");
    cJSON *jlon = cJSON_GetObjectItem(root, "lon");
    cJSON *jcity = cJSON_GetObjectItem(root, "city");
    if (!cJSON_IsNumber(jlat) || !cJSON_IsNumber(jlon)) {
        cJSON_Delete(root);
        return ESP_ERR_INVALID_RESPONSE;
    }
    *lat = jlat->valuedouble;
    *lon = jlon->valuedouble;
    if (!observer_location_valid(*lat, *lon)) {
        cJSON_Delete(root);
        return ESP_ERR_INVALID_RESPONSE;
    }
    if (city != NULL && cJSON_IsString(jcity)) {
        strlcpy(city, jcity->valuestring, city_len);
    }
    cJSON_Delete(root);
    ESP_LOGI(TAG, "IP geolocation: %.4f, %.4f (%s)", *lat, *lon, city ? city : "?");
    return ESP_OK;
}
