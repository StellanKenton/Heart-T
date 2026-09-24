# HeartThirdESP

ESP-IDF 5.5 的 ESP32-S3 下位机工程。保留 `Heart-T` 的 ADS1292R 默认配置、500 SPS 双通道采集、5 对采样一帧的 33 字节协议和 `help`、`status`、`time`、`version`、`reboot` 命令；将 STM32 HAL/SPI2、USB CDC、SEGGER RTT 分别替换为 ESP32-S3 GPIO/SPI2、Wi-Fi TCP 数据服务、TCP 日志命令服务。上位机滤波、显示及 CSV 工具位于 `HeartThirdCore`。

## 接线

默认硬件为 GPIO10–17 已引出的 ESP32-S3-DevKitC-1；下表均为 **GPIO 编号**，不是排针脚位序号。ADS1292R 模块信号名沿用原 STM32-V2.0 板卡；先核实手中模块丝印和电源电压。

| ADS1292R 模块 | ESP32-S3 | 方向 / 说明 |
| --- | --- | --- |
| DOUT / MISO | GPIO10 | ADS → ESP；SPI mode 1 |
| DIN / MOSI | GPIO11 | ESP → ADS |
| SCLK | GPIO12 | ESP → ADS；1 MHz |
| CS | GPIO13 | ESP → ADS；低有效 |
| PWDN / RESET | GPIO15 | ESP → ADS；低有效 |
| START | GPIO16 | ESP → ADS；高电平开始转换 |
| DRDY / DREDY | GPIO17 | ADS → ESP；下降沿中断 |
| GND | GND | 两板共地 |
| DVDD / VCC | 3V3（仅当模块支持 3.3 V） | ESP GPIO 只能接 3.3 V 逻辑；模块需要更高供电时必须做电平转换和单独供电 |
| CLKSEL | 3V3 | 选择 ADS 内部 512 kHz 时钟；如模块已有上拉，不重复硬连 |

电极 RA/LA/RL 仍接 ADS 模块原电极端，**不接 ESP GPIO**。默认 `RLD_SENS=0x00`，与原固件一致；RL 接口的具体行为由模块模拟电路决定。GPIO10–17 避开了 ESP32-S3 的启动配置脚、内部 Flash/PSRAM 常用脚及 USB 脚；若使用其他 S3 开发板，应先核对其板载外设是否占用这些引脚。参见[乐鑫 DevKitC-1 排针表](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.0.html)和[GPIO 说明](https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32s3/api-reference/peripherals/gpio.html)。

## 网络接口

固件每次启动自动连接 `rumi`，密码 `1234567890`；断线后自动重连，地址由路由器 DHCP 分配。电脑和 ESP 需能互相访问同一局域网。Wi-Fi 配置在 `main/port/transport.h`。

| 端口 | 协议 | 内容 |
| --- | --- | --- |
| 45670 | TCP | 原 33 字节二进制帧：`FA`、8 位帧序号、5 组 CH1/CH2 大端有符号 24 位、CRC-8/SMBUS；只向上位机发送 |
| 45671 | TCP | UTF-8 日志输出；发送以 `\n` 结尾的 ASCII 命令进行交互 |
| 45672 | UDP | 局域网发现：收到 `HEARTTHIRD_DISCOVER` 后回复 `HEARTTHIRD_ESP32S3` |

每个 TCP 端口同时服务一个客户端。网络发送与采集分任务，数据发送队列最多 32 帧；未连接或队列已满的样本会丢弃，并计入 `tcp_dropped`。`missed` 是 ADS DRDY 边沿间隔估计，两个计数含义不同。TCP 是字节流，接收端仍须按帧头和 CRC 解析，不应假设一次 `recv` 恰好返回 33 字节。日志队列最多 32 行，满时丢弃最旧日志；TCP 控制台重连后可使用 `status` 查询采集状态。

## 工程与构建

| 路径 | 职责 |
| --- | --- |
| `main/driver/ads1292r.c/.h` | 从 STM32 工程迁移的 ADS 配置、寄存器校验、DRDY 计数和 24 位采样解码 |
| `main/port/drvspi.c/.h` | ESP GPIO、SPI2 和片选时序绑定 |
| `main/port/system.c/.h` | 系统毫秒时钟和启动延时 |
| `main/port/log.c/.h` | `LOG_I/W/E` 有界日志队列 |
| `main/port/transport.c/.h` | Wi-Fi 连接、采集任务、TCP 数据/控制台服务和 UDP 发现 |
| `main/console.c/.h` | 从原控制台迁移的命令注册与解析器 |
| `main/main.c` | 启动装配及原系统调试命令 |

在仓库根目录使用 Device Tool 同名按钮或任务。Windows 命令入口：

```powershell
py -3 develop/quick_deploy.py deploy
py -3 develop/quick_deploy.py esp-build
$env:HEART_ESP_PORT = 'COM8'  # 按设备管理器中的 ESP32-S3 USB 端口修改
py -3 develop/quick_deploy.py esp-flash
py -3 develop/quick_deploy.py esp-reset
py -3 develop/quick_deploy.py esp-console
```

`esp-console` 默认用 UDP 查找设备；找不到时设置 `$env:HEART_ESP_HOST = '设备IP'`。首次烧录使用 USB 只是固件下载入口；采样、日志和交互均经 Wi-Fi TCP。Wi-Fi、lwIP TCP/IP 和系统网络事件任务在 CPU0；项目的启动、TCP 数据、TCP 日志命令、UDP 发现及 ADS 采集任务固定在 CPU1。ADS DRDY 中断在 CPU1 注册，采集任务优先级高于三个服务任务。当前工程不包含 STM32 HAL、USB CDC 和 SEGGER RTT 源码，也不编译原仓库中未参与采集的工具模块。
