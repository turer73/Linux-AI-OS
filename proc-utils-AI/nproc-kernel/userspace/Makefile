# Makefile - Linux-AI userspace tools
CC      ?= gcc
CFLAGS  := -Wall -Wextra -O2 -I../include
LDFLAGS :=

TOOLS := ai_ctl ai_status ai_permissions
PREFIX ?= /usr/local

.PHONY: all clean install

all: $(TOOLS)

ai_ctl: ai_ctl.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

ai_status: ai_status.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

ai_permissions: ai_permissions.c
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(TOOLS)

install: $(TOOLS)
	install -d $(DESTDIR)$(PREFIX)/bin
	install -m 755 ai_ctl $(DESTDIR)$(PREFIX)/bin/
	install -m 755 ai_status $(DESTDIR)$(PREFIX)/bin/
	install -m 755 ai_permissions $(DESTDIR)$(PREFIX)/bin/
