cmake_minimum_required(VERSION 3.22)

#
# This file is generated only once,
# and is not re-generated if converter is called multiple times.
#
# User is free to modify the file as much as necessary
#

# Setup compiler settings
set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS ON)


# Define the build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE "Debug")
endif()

# Set the project name
set(CMAKE_PROJECT_NAME Heart-T)

# Enable compile command to ease indexing with e.g. clangd
set(CMAKE_EXPORT_COMPILE_COMMANDS TRUE)

# Core project settings
project(${CMAKE_PROJECT_NAME})
message("Build type: " ${CMAKE_BUILD_TYPE})

# Enable CMake support for ASM and C languages
enable_language(C ASM)

# Create an executable object type
add_executable(${CMAKE_PROJECT_NAME})

# Add STM32CubeMX generated sources
add_subdirectory(cmake/stm32cubemx)

# SPI transactions also retain HAL DMA/GPIO helpers; fit the HAL in 64 KB Flash.
target_compile_options(STM32_Drivers PRIVATE -Os)

# Link directories setup
target_link_directories(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined library search paths
)

# Add sources to executable
target_sources(${CMAKE_PROJECT_NAME} PRIVATE
    user/driver/drvspi/drvspi.c
    user/driver/ads1292r/ads1292r.c
    user/app/system/system.c
    user/app/system/taskmanager.c
    user/module/log/log.c
    user/module/log/portLog.c
    user/module/log/console.c
    user/module/log/consoleRegisted/sysdebug.c
    user/module/log/SEGGER/SEGGER_RTT.c
    user/module/log/SEGGER/SEGGER_RTT_ASM_ARMv7M.S
    user/tools/ringbuffer/ringbuffer.c
)

# Add include paths
# Keep diagnostics and task assembly compact for the 64 KB Flash target, including Debug.
set_source_files_properties(
    user/driver/drvspi/drvspi.c
    user/driver/ads1292r/ads1292r.c
    user/app/system/system.c
    user/app/system/taskmanager.c
    user/module/log/log.c
    user/module/log/portLog.c
    user/module/log/console.c
    user/module/log/consoleRegisted/sysdebug.c
    user/module/log/SEGGER/SEGGER_RTT.c
    user/tools/ringbuffer/ringbuffer.c
    PROPERTIES COMPILE_OPTIONS "-Os"
)

target_include_directories(${CMAKE_PROJECT_NAME} PRIVATE
    user/driver/drvspi
    user/driver/ads1292r
    user/app/system
    user/module/log
    user/module/log/consoleRegisted
    user/module/log/SEGGER
    user/tools/ringbuffer
)

# Add project symbols (macros)
target_compile_definitions(${CMAKE_PROJECT_NAME} PRIVATE
    # Add user defined symbols
)

# Remove wrong libob.a library dependency when using cpp files
list(REMOVE_ITEM CMAKE_C_IMPLICIT_LINK_LIBRARIES ob)

# Add linked libraries
target_link_libraries(${CMAKE_PROJECT_NAME}
    stm32cubemx

    # Add user defined libraries
)
