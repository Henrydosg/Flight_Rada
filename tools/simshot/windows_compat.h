#pragma once
#include <time.h>
#include <stdlib.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include <sys/stat.h>

#ifdef _WIN32
/* The renderer does not create persistent tile caches. */
static inline int sim_mkdir(const char *path, int mode)
{
    (void)path; (void)mode;
    return -1;
}
#define mkdir(path, mode) sim_mkdir(path, mode)
static inline struct tm *sim_gmtime_r(const time_t *value, struct tm *out)
{
    return gmtime_s(out, value) == 0 ? out : NULL;
}
static inline struct tm *sim_localtime_r(const time_t *value, struct tm *out)
{
    return localtime_s(out, value) == 0 ? out : NULL;
}
#define gmtime_r sim_gmtime_r
#define localtime_r sim_localtime_r
#define timegm _mkgmtime
/* Host-only portability. This header never enters the ESP-IDF build. */
static inline int sim_setenv(const char *name, const char *value, int overwrite)
{
    if (!overwrite && getenv(name)) return 0;
    return _putenv_s(name, value);
}
#define setenv sim_setenv
time_t sim_wall_time(time_t *out);
#define time sim_wall_time
size_t strlcpy(char *dst, const char *src, size_t n);
size_t strlcat(char *dst, const char *src, size_t n);
char *strcasestr(const char *haystack, const char *needle);
#endif
