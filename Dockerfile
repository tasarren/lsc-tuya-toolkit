# Latch builder
FROM debian:bookworm-slim AS latch-builder
ENV LATCH_CC=arm-linux-gnueabi-gcc
ENV LATCH_INNER=1
RUN apt-get update -qq &&  \
    apt-get install -y -qq  \
    gcc-arm-linux-gnueabi \
    libc6-dev-armel-cross \
    cmake make \
    curl bzip2 file binutils ca-certificates
COPY build.sh mqtt_latch.c nobind.c /work/latch/
WORKDIR /work
ENTRYPOINT ["/bin/sh", "/work/latch/build.sh"]
