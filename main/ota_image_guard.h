#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

/* ESP image ABI offsets, asserted against the real IDF types at the caller.
 * Pure logic so the 16 MB / wrong-board rejection can be tested on host. */
#define W7_OTA_MIN_PREFIX 112

static inline bool w7_ota_image_compatible(const uint8_t *p, size_t length,
                                          const char *running_version,
                                          const char *running_project)
{
    if (!p || length < W7_OTA_MIN_PREFIX || !running_version || !running_project) return false;
    if (p[0] != 0xe9 || (p[3] >> 4) != 3 || p[12] != 9 || p[13] != 0) return false;
    if (p[32] != 0x32 || p[33] != 0x54 || p[34] != 0xcd || p[35] != 0xab) return false;
    if (!memchr(p + 48, '\0', 32) || !memchr(p + 80, '\0', 32)) return false;
    const char *version = (const char *)p + 48;
    const char *project = (const char *)p + 80;
    const char *incoming_variant = strchr(version, '-');
    const char *running_variant = strchr(running_version, '-');
    return incoming_variant && running_variant &&
           strcmp(incoming_variant, running_variant) == 0 &&
           strcmp(project, running_project) == 0;
}
