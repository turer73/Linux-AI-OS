cmake_minimum_required(VERSION 3.10)
project(proc_utils_AI)

set(CMAKE_C_STANDARD 99)
set(CMAKE_CXX_STANDARD 17)

# Compiler flags
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O2 -Wall")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O2 -Wall")

# Source directories
set(CPU_SRC     ${CMAKE_SOURCE_DIR}/proc-utils-AI/proc-CPUIO)
set(GPU_SRC     ${CMAKE_SOURCE_DIR}/proc-utils-AI/proc-GPUIO)
set(KERNEL_SRC  ${CMAKE_SOURCE_DIR}/proc-utils-AI/nproc-kernel)

# Output directory
set(BIN_DIR ${CMAKE_BINARY_DIR}/bin)
file(MAKE_DIRECTORY ${BIN_DIR})

# CPU binary (single entry point, headers included via proc-CPUIO.c)
add_executable(cpu_tools ${CPU_SRC}/proc-CPUIO.c)
target_include_directories(cpu_tools PRIVATE ${CPU_SRC})
target_link_libraries(cpu_tools pthread)
set_target_properties(cpu_tools PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${BIN_DIR})

# GPU binary
add_executable(gpu_tools ${GPU_SRC}/proc-GPUIO.cpp)
target_include_directories(gpu_tools PRIVATE ${GPU_SRC})
target_link_libraries(gpu_tools pthread)
set_target_properties(gpu_tools PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${BIN_DIR})

# Userspace tools (not kernel module - that requires separate kernel build)
add_executable(ai_ctl ${KERNEL_SRC}/userspace/ai_ctl.c)
target_include_directories(ai_ctl PRIVATE ${KERNEL_SRC}/include)
set_target_properties(ai_ctl PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${BIN_DIR})

add_executable(ai_status ${KERNEL_SRC}/userspace/ai_status.c)
target_include_directories(ai_status PRIVATE ${KERNEL_SRC}/include)
set_target_properties(ai_status PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${BIN_DIR})

add_executable(ai_permissions ${KERNEL_SRC}/userspace/ai_permissions.c)
target_include_directories(ai_permissions PRIVATE ${KERNEL_SRC}/include)
set_target_properties(ai_permissions PROPERTIES RUNTIME_OUTPUT_DIRECTORY ${BIN_DIR})
