/* Loopback MQTTS latch. One client, then exit once RTSP :88 is listening. */
#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <poll.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "mbedtls/ctr_drbg.h"
#include "mbedtls/entropy.h"
#include "mbedtls/error.h"
#include "mbedtls/net_sockets.h"
#include "mbedtls/pk.h"
#include "mbedtls/ssl.h"
#include "mbedtls/x509_crt.h"

static int bio_send(void *ctx, const unsigned char *buf, size_t len) {
    int fd = *(int *)ctx;
    ssize_t n = send(fd, buf, len, 0);
    if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return MBEDTLS_ERR_SSL_WANT_WRITE;
    if (n < 0) return MBEDTLS_ERR_NET_SEND_FAILED;
    return (int)n;
}

static int bio_recv(void *ctx, unsigned char *buf, size_t len) {
    int fd = *(int *)ctx;
    ssize_t n = recv(fd, buf, len, 0);
    if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) return MBEDTLS_ERR_SSL_WANT_READ;
    if (n < 0) return MBEDTLS_ERR_NET_RECV_FAILED;
    if (n == 0) return MBEDTLS_ERR_NET_CONN_RESET;
    return (int)n;
}

static int ssl_fd(mbedtls_ssl_context *ssl) {
    return *(int *)ssl->MBEDTLS_PRIVATE(p_bio);
}

static int ssl_read_full(mbedtls_ssl_context *ssl, unsigned char *buf, int len) {
    int got = 0;
    while (got < len) {
        int n = mbedtls_ssl_read(ssl, buf + got, (size_t)(len - got));
        if (n == MBEDTLS_ERR_SSL_WANT_READ || n == MBEDTLS_ERR_SSL_WANT_WRITE) {
            struct pollfd pfd;
            pfd.fd = ssl_fd(ssl);
            pfd.events = (n == MBEDTLS_ERR_SSL_WANT_WRITE) ? POLLOUT : POLLIN;
            if (poll(&pfd, 1, 30000) <= 0) return MBEDTLS_ERR_SSL_TIMEOUT;
            continue;
        }
        if (n <= 0) return n == 0 ? MBEDTLS_ERR_NET_CONN_RESET : n;
        got += n;
    }
    return 0;
}

static int ssl_write_full(mbedtls_ssl_context *ssl, const unsigned char *buf, int len) {
    int sent = 0;
    while (sent < len) {
        int n = mbedtls_ssl_write(ssl, buf + sent, (size_t)(len - sent));
        if (n == MBEDTLS_ERR_SSL_WANT_READ || n == MBEDTLS_ERR_SSL_WANT_WRITE) continue;
        if (n <= 0) return n == 0 ? MBEDTLS_ERR_NET_SEND_FAILED : n;
        sent += n;
    }
    return 0;
}

static int listen_loopback(int port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    int one = 1;
    struct sockaddr_in addr;
    if (fd < 0) return -1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_port = htons((unsigned short)port);
    addr.sin_addr.s_addr = htonl(INADDR_ANY);
    if (bind(fd, (struct sockaddr *)&addr, sizeof addr) != 0 || listen(fd, 1) != 0) {
        close(fd);
        return -1;
    }
    return fd;
}

/* Non-blocking connect. 1 when the port accepts, 0 otherwise. */
static int tcp_open(const char *host, int port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in addr;
    int flags;
    int rc;
    (void)host;
    if (fd < 0) return 0;
    flags = fcntl(fd, F_GETFL, 0);
    fcntl(fd, F_SETFL, flags | O_NONBLOCK);
    memset(&addr, 0, sizeof addr);
    addr.sin_family = AF_INET;
    addr.sin_port = htons((unsigned short)port);
    addr.sin_addr.s_addr = htonl(0x7f000001);
    rc = connect(fd, (struct sockaddr *)&addr, sizeof addr);
    if (rc != 0 && errno == EINPROGRESS) {
        struct pollfd pfd;
        pfd.fd = fd;
        pfd.events = POLLOUT;
        if (poll(&pfd, 1, 0) > 0) {
            int err = 0;
            socklen_t len = sizeof err;
            getsockopt(fd, SOL_SOCKET, SO_ERROR, &err, &len);
            rc = err == 0 ? 0 : -1;
        } else {
            rc = -1;
        }
    }
    close(fd);
    return rc == 0;
}

static int read_packet(mbedtls_ssl_context *ssl, unsigned char *hdr, unsigned char **body, int *len) {
    int value = 0;
    int mult = 1;
    int i;
    unsigned char b;
    int n;
    for (i = 0; i < 4; i++) {
        n = ssl_read_full(ssl, &b, 1);
        if (n != 0) return n;
        value += (b & 0x7f) * mult;
        mult *= 128;
        if ((b & 0x80) == 0) break;
    }
    if (value < 0 || value > 65536) return MBEDTLS_ERR_SSL_BAD_INPUT_DATA;
    *body = NULL;
    *len = value;
    if (value == 0) return 0;
    *body = malloc((size_t)value);
    if (*body == NULL) return MBEDTLS_ERR_SSL_ALLOC_FAILED;
    n = ssl_read_full(ssl, *body, value);
    if (n != 0) {
        free(*body);
        *body = NULL;
        return n;
    }
    (void)hdr;
    return 0;
}

static void suback(mbedtls_ssl_context *ssl, const unsigned char *body, int n) {
    unsigned char out[160];
    int count = 0;
    int i = 2;
    int rem;
    if (n < 2 || n > 140) return;
    while (i + 2 <= n) {
        int tlen = (body[i] << 8) | body[i + 1];
        i += 2 + tlen + 1;
        if (i > n) return;
        count++;
    }
    rem = 2 + count;
    if (rem + 2 > (int)sizeof out) return;
    out[0] = 0x90;
    out[1] = (unsigned char)rem;
    out[2] = body[0];
    out[3] = body[1];
    memset(out + 4, 0, (size_t)count);
    ssl_write_full(ssl, out, 4 + count);
}

static void puback(mbedtls_ssl_context *ssl, const unsigned char *body, int n) {
    unsigned char ack[4];
    int tlen;
    int off;
    if (n < 4) return;
    tlen = (body[0] << 8) | body[1];
    off = 2 + tlen;
    if (off + 2 > n) return;
    ack[0] = 0x40;
    ack[1] = 0x02;
    ack[2] = body[off];
    ack[3] = body[off + 1];
    ssl_write_full(ssl, ack, 4);
}

static int tls_setup(mbedtls_ssl_context *ssl, mbedtls_ssl_config *conf, mbedtls_x509_crt *crt,
                      mbedtls_pk_context *pk, mbedtls_entropy_context *entropy, mbedtls_ctr_drbg_context *drbg,
                      int *fd, const char *cert, const char *key) {
    static const int suites[] = { MBEDTLS_TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA256, 0 };
    int rc;
    mbedtls_ssl_init(ssl);
    mbedtls_ssl_config_init(conf);
    mbedtls_x509_crt_init(crt);
    mbedtls_pk_init(pk);
    mbedtls_entropy_init(entropy);
    mbedtls_ctr_drbg_init(drbg);
    rc = mbedtls_ctr_drbg_seed(drbg, mbedtls_entropy_func, entropy, (const unsigned char *)"mqtt_latch", 10);
    if (rc != 0) return rc;
    rc = mbedtls_x509_crt_parse_file(crt, cert);
    if (rc != 0) return rc;
    rc = mbedtls_pk_parse_keyfile(pk, key, NULL, mbedtls_ctr_drbg_random, drbg);
    if (rc != 0) return rc;
    rc = mbedtls_ssl_config_defaults(conf, MBEDTLS_SSL_IS_SERVER, MBEDTLS_SSL_TRANSPORT_STREAM, MBEDTLS_SSL_PRESET_DEFAULT);
    if (rc != 0) return rc;
    mbedtls_ssl_conf_min_tls_version(conf, MBEDTLS_SSL_VERSION_TLS1_2);
    mbedtls_ssl_conf_max_tls_version(conf, MBEDTLS_SSL_VERSION_TLS1_2);
    mbedtls_ssl_conf_ciphersuites(conf, suites);
    mbedtls_ssl_conf_authmode(conf, MBEDTLS_SSL_VERIFY_NONE);
    mbedtls_ssl_conf_rng(conf, mbedtls_ctr_drbg_random, drbg);
    rc = mbedtls_ssl_conf_own_cert(conf, crt, pk);
    if (rc != 0) return rc;
    rc = mbedtls_ssl_setup(ssl, conf);
    if (rc != 0) return rc;
    mbedtls_ssl_set_bio(ssl, fd, bio_send, bio_recv, NULL);
    while ((rc = mbedtls_ssl_handshake(ssl)) != 0) {
        if (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE) {
            struct pollfd pfd;
            pfd.fd = *fd;
            pfd.events = (rc == MBEDTLS_ERR_SSL_WANT_WRITE) ? POLLOUT : POLLIN;
            poll(&pfd, 1, 1000);
            continue;
        }
        return rc;
    }
    return 0;
}

static void serve(int fd, const char *cert, const char *key) {
    mbedtls_ssl_context ssl;
    mbedtls_ssl_config conf;
    mbedtls_x509_crt crt;
    mbedtls_pk_context pk;
    mbedtls_entropy_context entropy;
    mbedtls_ctr_drbg_context drbg;
    int flags = fcntl(fd, F_GETFL, 0);
    fcntl(fd, F_SETFL, flags | O_NONBLOCK);
    if (tls_setup(&ssl, &conf, &crt, &pk, &entropy, &drbg, &fd, cert, key) != 0) goto done;
    for (;;) {
        unsigned char hdr;
        unsigned char *body = NULL;
        int len = 0;
        int kind;
        int rc;
        struct pollfd pfd;
        if (tcp_open("127.0.0.1", 88)) break;
        rc = mbedtls_ssl_read(&ssl, &hdr, 1);
        if (rc == MBEDTLS_ERR_SSL_WANT_READ || rc == MBEDTLS_ERR_SSL_WANT_WRITE) {
            pfd.fd = fd;
            pfd.events = POLLIN;
            poll(&pfd, 1, 200);
            continue;
        }
        if (rc != 1) break;
        rc = read_packet(&ssl, &hdr, &body, &len);
        if (rc != 0) break;
        kind = hdr >> 4;
        switch (kind) {
        case 1:
            ssl_write_full(&ssl, (const unsigned char *)"\x20\x02\x00\x00", 4);
            break;
        case 8:
            suback(&ssl, body, len);
            break;
        case 3:
            if (hdr & 0x06) puback(&ssl, body, len);
            break;
        case 12:
            ssl_write_full(&ssl, (const unsigned char *)"\xd0\x00", 2);
            break;
        case 14:
            free(body);
            goto done;
        default:
            break;
        }
        free(body);
    }
done:
    mbedtls_ssl_free(&ssl);
    mbedtls_ssl_config_free(&conf);
    mbedtls_x509_crt_free(&crt);
    mbedtls_pk_free(&pk);
    mbedtls_ctr_drbg_free(&drbg);
    mbedtls_entropy_free(&entropy);
    close(fd);
}

int main(int argc, char **argv) {
    int listen_fd;
    int client;
    if (argc != 3) {
        fprintf(stderr, "usage: %s server.crt server.key\n", argv[0]);
        return 2;
    }
    listen_fd = listen_loopback(8883);
    if (listen_fd < 0) {
        perror("listen");
        return 1;
    }
    client = accept(listen_fd, NULL, NULL);
    close(listen_fd);
    if (client < 0) return 1;
    serve(client, argv[1], argv[2]);
    return 0;
}
