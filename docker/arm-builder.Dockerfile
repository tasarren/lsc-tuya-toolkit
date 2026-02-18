FROM debian:bookworm-slim
ENV PTZCTL_CC=arm-linux-gnueabi-gcc
ENV MOTOR_CC=arm-linux-gnueabi-gcc

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        gcc-arm-linux-gnueabi \
        libc6-dev-armel-cross \
        file \
    && rm -rf /var/lib/apt/lists/*

COPY --from=project /build_ptzctl.sh /work/build_ptzctl.sh
RUN chmod +x /work/build_ptzctl.sh

COPY --from=project /ptzlib/ /work/ptzlib/

WORKDIR /work
