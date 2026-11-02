#!/bin/sh
# This script starts remote access services like Telnet or FTP

LOG_FILENAME="remote"
. "/tmp/sd/custom/env.sh"
load_cfg
log "remote tools starting"

/bin/sh "${SCRIPTS_DIR}/telnet.sh" >/dev/null 2>&1 &
/bin/sh "${SCRIPTS_DIR}/ftp.sh" >/dev/null 2>&1 &