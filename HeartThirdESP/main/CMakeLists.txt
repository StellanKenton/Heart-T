idf_component_register(
    SRCS "main.c" "console.c" "driver/ads1292r.c"
         "port/drvspi.c" "port/system.c" "port/log.c" "port/transport.c"
    INCLUDE_DIRS "." "driver" "port"
    REQUIRES esp_driver_spi esp_driver_gpio esp_wifi esp_event esp_netif nvs_flash lwip esp_timer
)
