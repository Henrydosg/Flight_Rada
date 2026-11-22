cmake_minimum_required(VERSION 3.16)
# This checkout targets the user's physical 8 MB LCD-7. Plain `idf.py build`
# must not silently select the upstream 16 MB / auto-detected board defaults.
if(NOT DEFINED SDKCONFIG_DEFAULTS)
    set(SDKCONFIG_DEFAULTS "sdkconfig.defaults;sdkconfig.board.8mb;sdkconfig.board.waveshare7-8mb")
endif()
set(PROJECT_VER "0.4.7")
# Board-variant suffix: the 7B and Tab5 builds are not interchangeable with
# the standard 800x480 binary, and the OTA handler refuses a mismatched
# image based on this suffix.
if(SDKCONFIG_DEFAULTS MATCHES "waveshare7-8mb")
    set(PROJECT_VER "${PROJECT_VER}.1-w7-8mb-local")
elseif(DEFINED SDKCONFIG AND SDKCONFIG MATCHES "elecrow10")
    set(PROJECT_VER "${PROJECT_VER}-elecrow10")
elseif(DEFINED SDKCONFIG AND SDKCONFIG MATCHES "jc10v2")
    set(PROJECT_VER "${PROJECT_VER}-jc10-v2")
elseif(DEFINED SDKCONFIG AND SDKCONFIG MATCHES "jc10")
    set(PROJECT_VER "${PROJECT_VER}-jc10-v1")
elseif(DEFINED SDKCONFIG AND SDKCONFIG MATCHES "tab5c")
    set(PROJECT_VER "${PROJECT_VER}-tab5-c")
elseif(DEFINED SDKCONFIG AND SDKCONFIG MATCHES "tab5")
    set(PROJECT_VER "${PROJECT_VER}-tab5")
elseif(DEFINED SDKCONFIG_DEFAULTS AND SDKCONFIG_DEFAULTS MATCHES "7c")
    set(PROJECT_VER "${PROJECT_VER}-7c")
elseif((DEFINED SDKCONFIG_DEFAULTS AND SDKCONFIG_DEFAULTS MATCHES "7b") OR (DEFINED SDKCONFIG AND SDKCONFIG MATCHES "7b"))
    set(PROJECT_VER "${PROJECT_VER}-7b")
elseif(DEFINED SDKCONFIG_DEFAULTS AND SDKCONFIG_DEFAULTS MATCHES "crowpaneladv70")
    set(PROJECT_VER "${PROJECT_VER}-crowpaneladv70")
elseif(DEFINED SDKCONFIG_DEFAULTS AND SDKCONFIG_DEFAULTS MATCHES "crowpanel70")
    set(PROJECT_VER "${PROJECT_VER}-crowpanel70")
elseif(DEFINED SDKCONFIG_DEFAULTS AND SDKCONFIG_DEFAULTS MATCHES "crowpanel50")
    set(PROJECT_VER "${PROJECT_VER}-crowpanel")
elseif(DEFINED SDKCONFIG_DEFAULTS AND SDKCONFIG_DEFAULTS MATCHES "sunton70" AND SDKCONFIG_DEFAULTS MATCHES "4mb")
    set(PROJECT_VER "${PROJECT_VER}-sunton70-4mb")
elseif(DEFINED SDKCONFIG_DEFAULTS AND SDKCONFIG_DEFAULTS MATCHES "sunton70")
    set(PROJECT_VER "${PROJECT_VER}-sunton70")
elseif(DEFINED SDKCONFIG_DEFAULTS AND SDKCONFIG_DEFAULTS MATCHES "pandatouch")
    set(PROJECT_VER "${PROJECT_VER}-pandatouch")
elseif(DEFINED SDKCONFIG_DEFAULTS AND SDKCONFIG_DEFAULTS MATCHES "sunton43r")
    set(PROJECT_VER "${PROJECT_VER}-sunton43r")
elseif(DEFINED SDKCONFIG_DEFAULTS AND SDKCONFIG_DEFAULTS MATCHES "sunton43")
    set(PROJECT_VER "${PROJECT_VER}-sunton43")
endif()
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
add_compile_options("-Wno-attributes")
# LVGL object allocations go to PSRAM (internal RAM is reserved for task
# stacks and Wi-Fi buffers); falls back to internal when PSRAM is full.
add_compile_options("-DLV_MEM_CUSTOM_ALLOC(s)=heap_caps_malloc_prefer(s,2,(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT),MALLOC_CAP_8BIT)")
add_compile_options("-DLV_MEM_CUSTOM_FREE(p)=heap_caps_free(p)")
add_compile_options("-DLV_MEM_CUSTOM_REALLOC(p,s)=heap_caps_realloc_prefer(p,s,2,(MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT),MALLOC_CAP_8BIT)")
project(esp32flight)

# Fail before compilation, including when an old sdkconfig overrides defaults.
if(NOT CONFIG_IDF_TARGET_ESP32S3 OR NOT CONFIG_ESPTOOLPY_FLASHSIZE_8MB)
    message(FATAL_ERROR "This checkout requires ESP32-S3 and physical 8 MB flash. See tools/build_waveshare7.ps1.")
endif()
if(NOT CONFIG_CANFLIGHT_BOARD_WAVESHARE_7 OR NOT CONFIG_CANFLIGHT_WAVESHARE7_KNOWN_GOOD
   OR NOT CONFIG_SPIRAM_MODE_OCT OR NOT CONFIG_SPIRAM_SPEED_80M
   OR NOT CONFIG_EXAMPLE_LVGL_PORT_ROTATION_180
   OR NOT CONFIG_PARTITION_TABLE_CUSTOM_FILENAME STREQUAL "partitions-8mb.csv")
    message(FATAL_ERROR "Use the verified LCD-7/8MB/OPI80/180-degree profile; do not use 7B or 7C.")
endif()
add_custom_target(validate_waveshare7 ALL
    COMMAND ${PYTHON} "${CMAKE_SOURCE_DIR}/tools/validate_firmware.py" --build-dir "${CMAKE_BINARY_DIR}"
    DEPENDS gen_project_binary partition_table_bin bootloader spiffs_assets_bin
    VERBATIM)
