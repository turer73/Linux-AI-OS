CC       ?= gcc
CXX      ?= g++
CFLAGS   ?= -O2 -Wall -I. -I/usr/include
CXXFLAGS ?= -O2 -Wall -I. -I/usr/include
LDFLAGS  ?= -lpthread

BIN_DIR     := bin
CPU_SRC     := proc-utils-AI/proc-CPUIO
GPU_SRC     := proc-utils-AI/proc-GPUIO
KERNEL_SRC  := proc-utils-AI/nproc-kernel

.PHONY: all clean userspace kmod

all: $(BIN_DIR) $(BIN_DIR)/cpu_tools $(BIN_DIR)/gpu_tools userspace

$(BIN_DIR):
	@mkdir -p $(BIN_DIR)

$(BIN_DIR)/cpu_tools: $(CPU_SRC)/proc-CPUIO.c
	$(CC) $(CFLAGS) -I$(CPU_SRC) -o $@ $^ $(LDFLAGS)

$(BIN_DIR)/gpu_tools: $(GPU_SRC)/proc-GPUIO.cpp
	$(CXX) $(CXXFLAGS) -I$(GPU_SRC) -o $@ $^ $(LDFLAGS)

# Userspace tools (ai_ctl, ai_status, ai_permissions)
userspace: $(BIN_DIR)
	$(MAKE) -C $(KERNEL_SRC)/userspace CC=$(CC) CFLAGS="$(CFLAGS)"
	cp $(KERNEL_SRC)/userspace/ai_ctl $(BIN_DIR)/ 2>/dev/null || true
	cp $(KERNEL_SRC)/userspace/ai_status $(BIN_DIR)/ 2>/dev/null || true
	cp $(KERNEL_SRC)/userspace/ai_permissions $(BIN_DIR)/ 2>/dev/null || true

# Kernel module (requires linux-headers, run on target Linux system)
kmod:
	$(MAKE) -C $(KERNEL_SRC)/kmod

clean:
	rm -rf $(BIN_DIR) *.o
	$(MAKE) -C $(KERNEL_SRC)/userspace clean 2>/dev/null || true
	$(MAKE) -C $(KERNEL_SRC)/kmod clean 2>/dev/null || true
