/************************************************************************************
* @file     : log.h
* @brief    : Bounded TCP console log queue.
* @details  : Application writes formatted lines; the console task owns the socket.
***********************************************************************************/
#ifndef HEARTTHIRD_ESP_LOG_H
#define HEARTTHIRD_ESP_LOG_H
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define LOG_LINE_SIZE 256U
#define LOG_QUEUE_LENGTH 32U
#define LOG_E(tag, format, ...) logWrite('E', tag, format, ##__VA_ARGS__)
#define LOG_W(tag, format, ...) logWrite('W', tag, format, ##__VA_ARGS__)
#define LOG_I(tag, format, ...) logWrite('I', tag, format, ##__VA_ARGS__)
#define LOG_D(tag, format, ...) logWrite('D', tag, format, ##__VA_ARGS__)
typedef struct stLogLine {
    char text[LOG_LINE_SIZE];
} stLogLine;
bool logInit(void);
void logWrite(char level, const char *tag, const char *format, ...) __attribute__((format(printf, 3, 4)));
bool logTake(stLogLine *line, uint32_t waitMs);
#ifdef __cplusplus
}
#endif
#endif
/**************************End of file********************************/
