#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "ota_image_guard.h"

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #x); return 1; } } while (0)

int main(int argc, char **argv)
{
    CHECK(argc == 2);
    unsigned char prefix[288], test[288];
    FILE *f = fopen(argv[1], "rb");
    CHECK(f && fread(prefix, 1, sizeof(prefix), f) == sizeof(prefix));
    fclose(f);
    const char *version = "0.4.7-w7-8mb-local";
    CHECK(w7_ota_image_compatible(prefix, sizeof(prefix), version, "esp32flight"));
    for (size_t n = 0; n < W7_OTA_MIN_PREFIX; n++)
        CHECK(!w7_ota_image_compatible(prefix, n, version, "esp32flight"));
    memcpy(test, prefix, sizeof(test));
    test[3] = (test[3] & 0x0f) | 0x40;
    CHECK(!w7_ota_image_compatible(test, sizeof(test), version, "esp32flight"));
    memcpy(test, prefix, sizeof(test));
    test[12] = 0;
    CHECK(!w7_ota_image_compatible(test, sizeof(test), version, "esp32flight"));
    memcpy(test, prefix, sizeof(test));
    memset(test + 48, 0, 32);
    strcpy((char *)test + 48, "0.4.8-7b");
    CHECK(!w7_ota_image_compatible(test, sizeof(test), version, "esp32flight"));
    strcpy((char *)test + 48, "0.4.8-w7-8mb-local");
    CHECK(w7_ota_image_compatible(test, sizeof(test), version, "esp32flight"));
    memset(test + 48, 'X', 32);
    CHECK(!w7_ota_image_compatible(test, sizeof(test), version, "esp32flight"));
    CHECK(!w7_ota_image_compatible(prefix, sizeof(prefix), version, "another-project"));
    for (size_t step = 1; step <= sizeof(prefix); step++) {
        memset(test, 0, sizeof(test));
        for (size_t pos = 0; pos < sizeof(prefix); ) {
            size_t n = sizeof(prefix) - pos;
            if (n > step) n = step;
            memcpy(test + pos, prefix + pos, n);
            pos += n;
        }
        CHECK(w7_ota_image_compatible(test, sizeof(test), version, "esp32flight"));
    }
    puts("PASS: real binary OTA prefix, 16MB/wrong chip/board/project, unterminated identity, 288 fragmentation sizes");
    return 0;
}
