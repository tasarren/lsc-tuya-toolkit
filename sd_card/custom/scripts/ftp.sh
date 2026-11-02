#!/bin/sh
# This script starts up an anonymous FTP Service until we find a way to user passwd

LOG_FILENAME="ftp"
. "/tmp/sd/custom/env.sh"

# Defaults
FTP=0
FTP_PORT=21
load_cfg
log "FTP script starting"

ensure_ftp() {
    if [ "${FTP}" != "1" ]; then
      return
    fi

    if ps | grep -v grep | grep -q "tcpsvd 0 ${FTP_PORT}"; then
        return
    fi
    tcpsvd 0 "${FTP_PORT}" ftpd -a -w / -t 1800 &
    log "ftp started on port ${FTP_PORT}"
}
ensure_ftp