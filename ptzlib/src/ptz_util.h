#ifndef PTZ_UTIL_H
#define PTZ_UTIL_H

#include <stddef.h>
#include <time.h>

void ptz_sleep_us(long us);

/* Monotonic time helpers (useful for event-loop driven control). */
int ptz_now_monotonic(struct timespec *out);
int ptz_timespec_ge(const struct timespec *a, const struct timespec *b);
struct timespec ptz_timespec_add_us(struct timespec t, long us);

char *ptz_trim(char *s);
int ptz_clampi(int v, int lo, int hi);
int ptz_parse_int(const char *v, int def);
unsigned long ptz_parse_hex(const char *v, unsigned long def);

void ptz_mkdir_p_for_file(const char *path);

#endif /* PTZ_UTIL_H */
