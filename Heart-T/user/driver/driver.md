# Driver 目录

| 子目录 | 职责 | 主文档 |
| --- | --- | --- |
| `drvspi` | STM32G431 SPI1 阻塞事务和软件片选 | [drvspi.md](drvspi/drvspi.md) |
| `ads1292r` | ADS1292R 上电、配置、双通道数据采集 | [ads1292r.md](ads1292r/ads1292r.md) |

依赖：`ads1292r` → `drvspi`、`app/system`、STM32 HAL；`drvspi` → CubeMX SPI1、STM32 HAL/CMSIS。
两个驱动直接列入 `Heart-T/CMakeLists.txt`；不直接调用原生 RTOS API，不动态分配内存。
`app/system/taskmanager.c` 中的 `sensorProcess` 是设备和 SPI1 的唯一周期操作入口。
新增驱动目录时同步更新本索引和项目根 README。
