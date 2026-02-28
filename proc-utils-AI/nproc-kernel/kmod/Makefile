# Makefile - Build Linux-AI kernel module
# Usage:
#   make              - Build against running kernel
#   make clean        - Clean build artifacts
#   make install      - Install module
#   make dkms-install - Install via DKMS (recommended)

KDIR ?= /lib/modules/$(shell uname -r)/build
PWD  := $(shell pwd)

.PHONY: all clean install dkms-install dkms-remove

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean

install:
	$(MAKE) -C $(KDIR) M=$(PWD) modules_install
	depmod -a

dkms-install:
	@echo "Installing via DKMS..."
	cp -r ../. /usr/src/linux-ai-0.2.0/
	dkms add -m linux-ai -v 0.2.0
	dkms build -m linux-ai -v 0.2.0
	dkms install -m linux-ai -v 0.2.0

dkms-remove:
	dkms remove -m linux-ai -v 0.2.0 --all
	rm -rf /usr/src/linux-ai-0.2.0/
