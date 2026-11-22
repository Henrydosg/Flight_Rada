/* Offline-only Windows host shims; no network or device IO. */
#include <string.h>
#include <strings.h>
#include "esp_netif.h"
#include "web_server.h"

volatile bool g_app_background;

esp_err_t esp_netif_get_ip_info(esp_netif_t *netif, esp_netif_ip_info_t *info)
{
    (void)netif;
    memset(info, 0, sizeof(*info));
    return ESP_FAIL;
}

int wifi_mgr_last_reason(void) { return 0; }
void web_server_start(void) { }
void web_state_publish(const char *json) { (void)json; }
void web_metrics_publish(int count, int unique, int max_alt_ft, double nearest_km)
{
    (void)count; (void)unique; (void)max_alt_ft; (void)nearest_km;
}
bool web_state_wanted(void) { return false; }

char *strcasestr(const char *haystack, const char *needle)
{
    size_t n = strlen(needle);
    for (; *haystack; haystack++) {
        if (strncasecmp(haystack, needle, n) == 0) return (char *)haystack;
    }
    return n == 0 ? (char *)haystack : NULL;
}
