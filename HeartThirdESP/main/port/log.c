/************************************************************************************
* @file     : log.c
* @brief    : Format logs into a bounded FreeRTOS queue for TCP delivery.
* @details  : Oldest lines are discarded when the network console is absent.
***********************************************************************************/
#include "log.h"
#include "system.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

static QueueHandle_t gLogQueue;

/** @brief Allocate the fixed-depth log queue before other services start. */
bool logInit(void) {
    gLogQueue = xQueueCreate(LOG_QUEUE_LENGTH, sizeof(stLogLine));
    return gLogQueue != NULL;
}

/** @brief Queue one bounded line without blocking acquisition. */
void logWrite(char level, const char *tag, const char *format, ...) {
    stLogLine lLine = {0};
    stLogLine lDiscard;
    va_list lArgs;
    int lPrefix;
    size_t lLength;
    if (gLogQueue == NULL || format == NULL) {
        return;
    }
    lPrefix = snprintf(lLine.text, sizeof(lLine.text), "[%c][%lu][%s] ", level,
                       (unsigned long)systemGetTickMs(), tag == NULL ? "" : tag);
    if (lPrefix < 0 || (size_t)lPrefix >= sizeof(lLine.text) - 3U) {
        return;
    }
    va_start(lArgs, format);
    vsnprintf(lLine.text + lPrefix, sizeof(lLine.text) - (size_t)lPrefix - 2U, format, lArgs);
    va_end(lArgs);
    lLength = strlen(lLine.text);
    lLine.text[lLength++] = '\r';
    lLine.text[lLength++] = '\n';
    lLine.text[lLength] = '\0';
    if (xQueueSend(gLogQueue, &lLine, 0) != pdTRUE) {
        (void)xQueueReceive(gLogQueue, &lDiscard, 0);
        (void)xQueueSend(gLogQueue, &lLine, 0);
    }
}

/** @brief Read one line in the console task. */
bool logTake(stLogLine *line, uint32_t waitMs) {
    return line != NULL && gLogQueue != NULL &&
           xQueueReceive(gLogQueue, line, pdMS_TO_TICKS(waitMs)) == pdTRUE;
}
/**************************End of file********************************/
