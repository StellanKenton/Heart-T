/************************************************************************************
* @file     : transport.c
* @brief    : Wi-Fi station, ADS acquisition and TCP services for ESP32-S3.
* @details  : Separate tasks keep slow TCP clients out of the 500 SPS sample path.
***********************************************************************************/
#include "transport.h"
#include "ads1292r.h"
#include "console.h"
#include "log.h"
#include "system.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "lwip/inet.h"
#include "lwip/sockets.h"
#include <errno.h>
#include <stddef.h>
#include <string.h>

static QueueHandle_t gFrameQueue;
static esp_netif_t *gStation;
static volatile bool gWifiConnected;
static volatile bool gDataConnected;
static volatile bool gSensorReady;
static volatile bool gSensorFault;
static int gConsoleClient = -1;
static TaskHandle_t gAcquisitionTask;
static uint32_t gDroppedSamples;
static uint8_t gSampleCount;
static uint8_t gFrameSequence;
static stHeartFrame gPendingFrame;

/** @brief Wake the high-priority sampling task on each DRDY edge. */
void transportDrdyIrq(void) {
    BaseType_t lWoken = pdFALSE;
    if (gAcquisitionTask != NULL) {
        vTaskNotifyGiveFromISR(gAcquisitionTask, &lWoken);
        if (lWoken == pdTRUE) {
            portYIELD_FROM_ISR();
        }
    }
}

/** @brief Calculate CRC-8/SMBUS over the original sequence and payload. */
static uint8_t transportCrc(const uint8_t *data, uint32_t length) {
    uint8_t lCrc = 0U;
    uint32_t lIndex;
    uint32_t lBit;
    for (lIndex = 0U; lIndex < length; ++lIndex) {
        lCrc ^= data[lIndex];
        for (lBit = 0U; lBit < 8U; ++lBit) {
            lCrc = (uint8_t)((lCrc & 0x80U) ? ((uint32_t)lCrc << 1U) ^ 0x07U : (uint32_t)lCrc << 1U);
        }
    }
    return lCrc;
}

/** @brief Assemble one simultaneous channel pair into the 33-byte protocol. */
void transportQueueSample(const int32_t channel[2]) {
    uint32_t lChannel;
    uint32_t lCode;
    uint32_t lOffset;
    if (channel == NULL || gFrameQueue == NULL) {
        return;
    }
    if (gSampleCount == 0U) {
        gPendingFrame.bytes[0] = 0xFAU;
        gPendingFrame.bytes[1] = gFrameSequence;
    }
    for (lChannel = 0U; lChannel < 2U; ++lChannel) {
        lCode = (uint32_t)channel[lChannel];
        lOffset = 2U + (uint32_t)gSampleCount * 6U + lChannel * 3U;
        gPendingFrame.bytes[lOffset] = (uint8_t)(lCode >> 16U);
        gPendingFrame.bytes[lOffset + 1U] = (uint8_t)(lCode >> 8U);
        gPendingFrame.bytes[lOffset + 2U] = (uint8_t)lCode;
    }
    if (++gSampleCount == HEART_SAMPLES_PER_FRAME) {
        gPendingFrame.bytes[HEART_FRAME_SIZE - 1U] = transportCrc(&gPendingFrame.bytes[1], HEART_FRAME_SIZE - 2U);
        gSampleCount = 0U;
        ++gFrameSequence;
        if (!gDataConnected || xQueueSend(gFrameQueue, &gPendingFrame, 0) != pdTRUE) {
            gDroppedSamples += HEART_SAMPLES_PER_FRAME;
        }
    }
}

/** @brief Return frames discarded while disconnected or while the TCP task is slow. */
uint32_t transportDroppedSamples(void) {
    return gDroppedSamples;
}

/** @brief Report Wi-Fi state to console commands. */
bool transportWifiConnected(void) {
    return gWifiConnected;
}

/** @brief Report the same INIT/NORMAL/FAULT sensor states as the STM32 build. */
const char *transportSensorMode(void) {
    return gSensorFault ? "FAULT" : (gSensorReady ? "NORMAL" : "INIT");
}

/** @brief Copy the current DHCP address for diagnostics. */
void transportGetIp(char *buffer, uint32_t size) {
    esp_netif_ip_info_t lInfo;
    if (buffer == NULL || size == 0U) {
        return;
    }
    buffer[0] = '\0';
    if (gWifiConnected && gStation != NULL && esp_netif_get_ip_info(gStation, &lInfo) == ESP_OK) {
        (void)esp_ip4addr_ntoa(&lInfo.ip, buffer, (int)size);
    }
}

/** @brief Reconnect after an access-point drop and announce DHCP changes. */
static void transportWifiEvent(void *argument, esp_event_base_t base, int32_t id, void *data) {
    (void)argument;
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        (void)esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        gWifiConnected = false;
        LOG_W("wifi", "disconnected; reconnecting");
        (void)esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *lEvent = (ip_event_got_ip_t *)data;
        gWifiConnected = true;
        LOG_I("wifi", "connected to %s, IP=" IPSTR, HEART_WIFI_SSID, IP2STR(&lEvent->ip_info.ip));
    }
}

/** @brief Initialize NVS and automatically join the configured Wi-Fi on every boot. */
static bool transportWifiStart(void) {
    wifi_init_config_t lInit = WIFI_INIT_CONFIG_DEFAULT();
    wifi_config_t lConfig = {0};
    esp_err_t lStatus = nvs_flash_init();
    if (lStatus == ESP_ERR_NVS_NO_FREE_PAGES || lStatus == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        if (nvs_flash_erase() != ESP_OK) {
            return false;
        }
        lStatus = nvs_flash_init();
    }
    if (lStatus != ESP_OK || esp_netif_init() != ESP_OK || esp_event_loop_create_default() != ESP_OK) {
        return false;
    }
    gStation = esp_netif_create_default_wifi_sta();
    if (gStation == NULL || esp_wifi_init(&lInit) != ESP_OK ||
        esp_event_handler_register(WIFI_EVENT, ESP_EVENT_ANY_ID, transportWifiEvent, NULL) != ESP_OK ||
        esp_event_handler_register(IP_EVENT, IP_EVENT_STA_GOT_IP, transportWifiEvent, NULL) != ESP_OK) {
        return false;
    }
    memcpy(lConfig.sta.ssid, HEART_WIFI_SSID, sizeof(HEART_WIFI_SSID) - 1U);
    memcpy(lConfig.sta.password, HEART_WIFI_PASSWORD, sizeof(HEART_WIFI_PASSWORD) - 1U);
    if (esp_wifi_set_mode(WIFI_MODE_STA) != ESP_OK ||
        esp_wifi_set_config(WIFI_IF_STA, &lConfig) != ESP_OK ||
        esp_wifi_set_ps(WIFI_PS_NONE) != ESP_OK || esp_wifi_start() != ESP_OK) {
        return false;
    }
    return true;
}

/** @brief Create one reusable listening socket. */
static int transportListen(uint16_t port) {
    struct sockaddr_in lAddress = {0};
    int lSocket = socket(AF_INET, SOCK_STREAM, IPPROTO_IP);
    int lReuse = 1;
    if (lSocket < 0) {
        return -1;
    }
    lAddress.sin_family = AF_INET;
    lAddress.sin_addr.s_addr = htonl(INADDR_ANY);
    lAddress.sin_port = htons(port);
    (void)setsockopt(lSocket, SOL_SOCKET, SO_REUSEADDR, &lReuse, sizeof(lReuse));
    if (bind(lSocket, (struct sockaddr *)&lAddress, sizeof(lAddress)) != 0 || listen(lSocket, 1) != 0) {
        close(lSocket);
        return -1;
    }
    return lSocket;
}

/** @brief Complete a short frame or log line despite partial TCP writes. */
static bool transportSendAll(int client, const uint8_t *data, size_t length) {
    size_t lSent = 0U;
    int lCount;
    while (lSent < length) {
        lCount = send(client, data + lSent, length - lSent, 0);
        if (lCount <= 0) {
            return false;
        }
        lSent += (size_t)lCount;
    }
    return true;
}

/** @brief Send queued logs before a command-triggered reboot. Console task only. */
void transportFlushLogs(void) {
    stLogLine lLine;
    if (gConsoleClient < 0) {
        return;
    }
    while (logTake(&lLine, 0)) {
        if (!transportSendAll(gConsoleClient, (const uint8_t *)lLine.text, strlen(lLine.text))) {
            return;
        }
    }
}

/** @brief Stream whole 33-byte frames; never block the acquisition task. */
static void transportDataTask(void *argument) {
    stHeartFrame lFrame;
    struct timeval lTimeout = {.tv_sec = 1, .tv_usec = 0};
    int lServer;
    int lClient;
    (void)argument;
    lServer = transportListen(HEART_DATA_PORT);
    if (lServer < 0) {
        LOG_E("tcp", "data listen failed");
        vTaskDelete(NULL);
        return;
    }
    for (;;) {
        lClient = accept(lServer, NULL, NULL);
        if (lClient < 0) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }
        (void)setsockopt(lClient, SOL_SOCKET, SO_SNDTIMEO, &lTimeout, sizeof(lTimeout));
        while (xQueueReceive(gFrameQueue, &lFrame, 0) == pdTRUE) {
            /* Discard frames from a previous client session. */
        }
        gDataConnected = true;
        LOG_I("tcp", "data client connected");
        for (;;) {
            if (xQueueReceive(gFrameQueue, &lFrame, pdMS_TO_TICKS(500)) != pdTRUE) {
                continue;
            }
            if (!transportSendAll(lClient, lFrame.bytes, sizeof(lFrame.bytes))) {
                break;
            }
        }
        gDataConnected = false;
        shutdown(lClient, SHUT_RDWR);
        close(lClient);
        LOG_W("tcp", "data client disconnected");
    }
}

/** @brief Serve logs and line-oriented commands on a separate TCP connection. */
static void transportConsoleTask(void *argument) {
    char lInput[128];
    struct timeval lTimeout = {.tv_sec = 0, .tv_usec = 20000};
    int lServer;
    int lClient;
    int lCount;
    (void)argument;
    lServer = transportListen(HEART_CONSOLE_PORT);
    if (lServer < 0) {
        LOG_E("tcp", "console listen failed");
        vTaskDelete(NULL);
        return;
    }
    for (;;) {
        lClient = accept(lServer, NULL, NULL);
        if (lClient < 0) {
            vTaskDelay(pdMS_TO_TICKS(100));
            continue;
        }
        (void)setsockopt(lClient, SOL_SOCKET, SO_RCVTIMEO, &lTimeout, sizeof(lTimeout));
        (void)setsockopt(lClient, SOL_SOCKET, SO_SNDTIMEO, &lTimeout, sizeof(lTimeout));
        gConsoleClient = lClient;
        consoleResetInput();
        LOG_I("tcp", "console connected; type help for commands");
        for (;;) {
            transportFlushLogs();
            lCount = recv(lClient, lInput, sizeof(lInput), 0);
            if (lCount > 0) {
                consoleFeed(lInput, (uint32_t)lCount);
            } else if (lCount == 0 || (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR)) {
                break;
            }
        }
        gConsoleClient = -1;
        shutdown(lClient, SHUT_RDWR);
        close(lClient);
    }
}

/** @brief Reply to LAN broadcast discovery so the host can find DHCP addresses. */
static void transportDiscoveryTask(void *argument) {
    struct sockaddr_in lAddress = {0};
    struct sockaddr_in lPeer;
    socklen_t lPeerLength;
    char lRequest[64];
    int lSocket;
    int lCount;
    (void)argument;
    lSocket = socket(AF_INET, SOCK_DGRAM, IPPROTO_IP);
    if (lSocket < 0) {
        vTaskDelete(NULL);
        return;
    }
    lAddress.sin_family = AF_INET;
    lAddress.sin_addr.s_addr = htonl(INADDR_ANY);
    lAddress.sin_port = htons(HEART_DISCOVERY_PORT);
    if (bind(lSocket, (struct sockaddr *)&lAddress, sizeof(lAddress)) != 0) {
        close(lSocket);
        vTaskDelete(NULL);
        return;
    }
    for (;;) {
        lPeerLength = sizeof(lPeer);
        lCount = recvfrom(lSocket, lRequest, sizeof(lRequest) - 1U, 0,
                          (struct sockaddr *)&lPeer, &lPeerLength);
        if (lCount > 0 && gWifiConnected) {
            lRequest[lCount] = '\0';
            if (strcmp(lRequest, HEART_DISCOVERY_REQUEST) == 0) {
                (void)sendto(lSocket, HEART_DISCOVERY_REPLY, sizeof(HEART_DISCOVERY_REPLY) - 1U,
                             0, (struct sockaddr *)&lPeer, lPeerLength);
            }
        }
    }
}

/** @brief Preserve the STM32 converter setup and one-second acquisition report. */
static void transportAcquisitionTask(void *argument) {
    stAds1292rConfig lConfig;
    stAds1292rSample lSample;
    stAds1292rStats lStats;
    uint32_t lLastReport;
    uint32_t lLastCount = 0U;
    uint32_t lLastError = 0U;
    int8_t lStatus;
    (void)argument;
    gAcquisitionTask = xTaskGetCurrentTaskHandle();
    (void)ads1292rLoadDefaultConfig(&lConfig);
    lStatus = ads1292rInit(&lConfig);
    if (lStatus == ADS1292R_OK) {
        (void)ulTaskNotifyTake(pdTRUE, 0);
        lStatus = ads1292rStart();
    }
    if (lStatus != ADS1292R_OK) {
        gSensorFault = true;
        LOG_E("ads1292r", "init/start failed status=%d; console remains available", (int)lStatus);
        vTaskDelete(NULL);
        return;
    }
    gSensorReady = true;
    LOG_I("ads1292r", "500 SPS gain=6 ECG=CH2 RLD_SENS=0x%02X verified", (unsigned)lConfig.rldSense);
    lLastReport = systemGetTickMs();
    for (;;) {
        if (ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(1000)) != 0U) {
            lStatus = ads1292rReadSample(&lSample);
            if (lStatus == ADS1292R_OK) {
                transportQueueSample(lSample.channel);
            } else if (lStatus != ADS1292R_ERROR_NOT_READY &&
                       (uint32_t)(systemGetTickMs() - lLastError) >= 1000U) {
                lLastError = systemGetTickMs();
                LOG_E("ads1292r", "sample failed status=%d", (int)lStatus);
            }
        }
        if ((uint32_t)(systemGetTickMs() - lLastReport) >= 1000U) {
            lLastReport = systemGetTickMs();
            (void)ads1292rGetStats(&lStats);
            if (lStats.sampleCount == lLastCount) {
                LOG_W("ads1292r", "no new samples; check DRDY GPIO17 and CLKSEL");
            } else {
                LOG_I("ads1292r", "samples=%lu missed=%lu tcp_dropped=%lu ch1=%ld ch2=%ld",
                      (unsigned long)lStats.sampleCount, (unsigned long)lStats.missedCount,
                      (unsigned long)gDroppedSamples, (long)lSample.channel[0], (long)lSample.channel[1]);
            }
            lLastCount = lStats.sampleCount;
        }
    }
}

/** @brief Start the station and the three independent network services. */
bool transportStart(void) {
    gFrameQueue = xQueueCreate(HEART_FRAME_QUEUE_LENGTH, sizeof(stHeartFrame));
    if (gFrameQueue == NULL || !transportWifiStart()) {
        return false;
    }
    return xTaskCreatePinnedToCore(transportDataTask, "heart_data", 4096, NULL, 5, NULL, 1) == pdPASS &&
           xTaskCreatePinnedToCore(transportConsoleTask, "heart_console", 4096, NULL, 4, NULL, 1) == pdPASS &&
           xTaskCreatePinnedToCore(transportDiscoveryTask, "heart_discovery", 3072, NULL, 3, NULL, 1) == pdPASS &&
           xTaskCreatePinnedToCore(transportAcquisitionTask, "heart_ads", 4096, NULL, 20, NULL, 1) == pdPASS;
}
/**************************End of file********************************/
