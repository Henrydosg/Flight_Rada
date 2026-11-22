#include "path_remap.h"

#undef fopen
#undef stat
#undef unlink
#undef rename

#include <stdio.h>
#include <string.h>
#include <errno.h>

static char s_base[512] = "assets";   /* dir with the device /assets content */

void apk_paths_set_base(const char *dir)
{
    snprintf(s_base, sizeof(s_base), "%s", dir);
}

static const char *remap(const char *path, char *buf, size_t n)
{
    if (strncmp(path, "/assets/", 8) == 0) {
        snprintf(buf, n, "%s/%s", s_base, path + 8);
        return buf;
    }
    return path;
}

FILE *apk_fopen(const char *path, const char *mode)
{
#ifdef SIMSHOT
    /* Snapshot rendering must not bake test history or caches into the
     * production SPIFFS source tree. Screenshot paths remain writable. */
    if (strncmp(path, "/assets/", 8) == 0 && strpbrk(mode, "wa+") != NULL) {
        errno = EACCES;
        return NULL;
    }
#endif
    char buf[640];
    return fopen(remap(path, buf, sizeof(buf)), mode);
}

int apk_stat(const char *path, struct stat *st)
{
    char buf[640];
    return stat(remap(path, buf, sizeof(buf)), st);
}

int apk_unlink(const char *path)
{
#ifdef SIMSHOT
    if (strncmp(path, "/assets/", 8) == 0) { errno = EACCES; return -1; }
#endif
    char buf[640];
    return unlink(remap(path, buf, sizeof(buf)));
}

int apk_rename(const char *from, const char *to)
{
#ifdef SIMSHOT
    if (strncmp(from, "/assets/", 8) == 0 || strncmp(to, "/assets/", 8) == 0) {
        errno = EACCES;
        return -1;
    }
#endif
    char b1[640], b2[640];
    return rename(remap(from, b1, sizeof(b1)), remap(to, b2, sizeof(b2)));
}

/* CA bundle for the curl-backed HTTP layers (Android: extracted cacert.pem) */
static char s_cainfo[640];

void apk_http_set_cainfo(const char *path)
{
    snprintf(s_cainfo, sizeof(s_cainfo), "%s", path);
}

const char *apk_http_cainfo(void)
{
    return s_cainfo[0] ? s_cainfo : (const char *)0;
}
