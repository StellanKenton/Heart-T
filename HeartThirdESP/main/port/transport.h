/************************************************************************************
* @file     : transport.h
* @brief    : Wi-Fi station and independent data, console and discovery servers.
* @details  : The 33-byte sample protocol is unchanged from the STM32 build.
***********************************************************************************/
#ifndef HEARTTHIRD_ESP_TRANSPORT_H
#define HEARTTHIRD_ESP_TRANSPORT_H
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define HEART_WIFI_SSID "rumi"
#define HEART_WIFI_PASSWORD "1234567890"
#define HEART_DATA_PORT 45670
#define HEART_CONSOLE_PORT 45671
#define HEART_DISCOVERY_PORT 45672
#define HEART_DISCOVERY_REQUEST "HEARTTHIRD_DISCOVER"
#define HEART_DISCOVERY_REPLY "HEARTTHIRD_ESP32S3"
#define HEART_FRAME_SIZE 33U
#define HEART_SAMPLES_PER_FRAME 5U
#define HEART_FRAME_QUEUE_LENGTH 32U
#define HEART_CONSOLE_COMMAND_SIZE 256U
typedef struct stHeartFrame {
    uint8_t bytes[HEART_FRAME_SIZE];
} stHeartFrame;
bool transportStart(void);
void transportQueueSample(const int32_t channel[2]);
uint32_t transportDroppedSamples(void);
bool transportWifiConnected(void);
const char *transportSensorMode(void);
bool transportSetBreath(bool enabled);
bool transportBreathEnabled(void);
void transportGetIp(char *buffer, uint32_t size);
void transportFlushLogs(void);
/* Called from the GPIO DRDY interrupt after the converter edge counter updates. */
void transportDrdyIrq(void);
#ifdef __cplusplus
}
#endif
#endif
/**************************End of file********************************/
