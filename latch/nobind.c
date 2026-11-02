/* LD_PRELOAD for anyka_ipc: ignore SO_BINDTODEVICE so MQTT can reach 127.0.0.1.
 * Built without libc; errno comes from the camera's uClibc at load time. */

#define SOL_SOCKET 1
#define SO_BINDTODEVICE 25
#define NR_SETSOCKOPT 294

extern int *__errno_location(void);

int setsockopt(int fd, int level, int name, const void *val, unsigned int len) {
    if (level == SOL_SOCKET && name == SO_BINDTODEVICE) return 0;
    register long r0 __asm__("r0") = fd;
    register long r1 __asm__("r1") = level;
    register long r2 __asm__("r2") = name;
    register long r3 __asm__("r3") = (long)val;
    register long r4 __asm__("r4") = (long)len;
    register long r7 __asm__("r7") = NR_SETSOCKOPT;
    __asm__ volatile("svc 0" : "+r"(r0) : "r"(r1), "r"(r2), "r"(r3), "r"(r4), "r"(r7) : "memory");
    if (r0 < 0 && r0 > -4096) {
        *__errno_location() = (int)-r0;
        return -1;
    }
    return (int)r0;
}
