cmake_minimum_required(VERSION 4.1)
project(release C)

set(CMAKE_C_STANDARD 11)

include_directories(src)

add_executable(release
        src/ptz_cli.c
        src/ptz_config.c
        src/ptz_core.c
        src/ptz_internal.h
        src/ptz_log.c
        src/ptz_motor.c
        src/ptz_state.c
        src/ptz_util.c
        src/ptz_util.h
        src/ptz_worker.c
        src/ptzctl.h)
