#define _POSIX_C_SOURCE 200809L

#include "ptz_util.h"

#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

void ptz_sleep_us(long us) {
    if (us <= 0) return;
    struct timespec ts;
    ts.tv_sec = us / 1000000L;
    ts.tv_nsec = (us % 1000000L) * 1000L;
    while (nanosleep(&ts, &ts) == -1 && errno == EINTR) {
        /* retry with remaining ts */
    }
}

int ptz_now_monotonic(struct timespec *out) {
    if (!out) return -1;
    return clock_gettime(CLOCK_MONOTONIC, out);
}

int ptz_timespec_ge(const struct timespec *a, const struct timespec *b) {
    if (!a || !b) return 0;
    if (a->tv_sec > b->tv_sec) return 1;
    if (a->tv_sec < b->tv_sec) return 0;
    return a->tv_nsec >= b->tv_nsec;
}

struct timespec ptz_timespec_add_us(struct timespec t, long us) {
    if (us <= 0) return t;
    long add_sec = us / 1000000L;
    long add_ns  = (us % 1000000L) * 1000L;

    t.tv_sec += add_sec;
    t.tv_nsec += add_ns;
    if (t.tv_nsec >= 1000000000L) {
        t.tv_sec += t.tv_nsec / 1000000000L;
        t.tv_nsec = t.tv_nsec % 1000000000L;
    }
    return t;
}

char *ptz_trim(char *s) {
    while (*s && isspace((unsigned char)*s)) s++;
    if (!*s) return s;
    char *e = s + strlen(s) - 1;
    while (e > s && isspace((unsigned char)*e)) *e-- = '\0';
    return s;
}

int ptz_clampi(int v, int lo, int hi) {
    if (v < lo) return lo;
    if (v > hi) return hi;
    return v;
}

int ptz_parse_int(const char *v, int def) {
    if (!v || !*v) return def;
    char *e = NULL;
    long n = strtol(v, &e, 0);
    return (e == v) ? def : (int)n;
}

unsigned long ptz_parse_hex(const char *v, unsigned long def) {
    if (!v || !*v) return def;
    char *e = NULL;

    if (v[0] == '0' && (v[1] == 'x' || v[1] == 'X')) {
        unsigned long n = strtoul(v, &e, 16);
        return (e != v && *e == '\0') ? n : def;
    }

    unsigned long n = strtoul(v, &e, 0);
    if (e != v && *e == '\0') return n;

    e = NULL;
    n = strtoul(v, &e, 16);
    return (e != v && *e == '\0') ? n : def;
}

void ptz_mkdir_p_for_file(const char *path) {
    if (!path || !*path) return;
    char tmp[512];
    snprintf(tmp, sizeof(tmp), "%s", path);
    for (char *p = tmp + 1; *p; p++) {
        if (*p == '/') {
            *p = '\0';
            (void)mkdir(tmp, 0755);
            *p = '/';
        }
    }
}
