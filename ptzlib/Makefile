CC ?= gcc
AR ?= ar

CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Wpedantic
CPPFLAGS ?=

LIB_OBJS = src/ptz_util.o src/ptz_config.o src/ptz_log.o src/ptz_motor.o src/ptz_worker.o src/ptz_state.o src/ptz_core.o
CLI_OBJS = src/ptz_cli.o

all: libptzctl.a ptzctl

libptzctl.a: $(LIB_OBJS)
	$(AR) rcs $@ $^

ptzctl: $(CLI_OBJS) libptzctl.a
	$(CC) $(CFLAGS) -o $@ $(CLI_OBJS) libptzctl.a $(LDFLAGS)

%.o: %.c
	$(CC) $(CPPFLAGS) $(CFLAGS) -c $< -o $@

clean:
	rm -f *.o libptzctl.a ptzctl

.PHONY: all clean
