# HeartThirdESP

ESP-IDF 5.5 的 ESP32-S3 下位机工程。使用 ADS1292R 以 500 SPS 双通道采集，保留 5 对采样一帧的 33 字节协议及原控制台命令，并增加 `breath on|off` 和 `rld on|off`；将 STM32 HAL/SPI2、USB CDC、SEGGER RTT 分别替换为 ESP32-S3 GPIO/SPI2、Wi-Fi TCP 数据服务、TCP 日志命令服务。上位机滤波、显示及 CSV 工具位于 `HeartThirdCore`。

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

电极 RA/LA/RL 仍接 ADS 模块原电极端，**不接 ESP GPIO**。默认 `RLD_SENS=0xC0`：关闭 RLD，保留 fMOD/4 PGA 斩波。`rld on` 使用厂家参考值 `0xEC`，开启 RLD 并取 CH2 正负输入作反馈；`rld off` 恢复 `0xC0`。RL 接口的具体行为由模块模拟电路决定；软件配置不能证明反馈网络正确。GPIO10–17 避开了 ESP32-S3 的启动配置脚、内部 Flash/PSRAM 常用脚及 USB 脚；若使用其他 S3 开发板，应先核对其板载外设是否占用这些引脚。参见[乐鑫 DevKitC-1 排针表](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.0.html)和[GPIO 说明](https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32s3/api-reference/peripherals/gpio.html)。

## 网络接口

固件每次启动自动连接 `rumi`，密码 `1234567890`；断线后自动重连，地址由路由器 DHCP 分配。电脑和 ESP 需能互相访问同一局域网。Wi-Fi 配置在 `main/port/transport.h`。

| 端口 | 协议 | 内容 |
| --- | --- | --- |
| 45670 | TCP | 原 33 字节二进制帧：`FA`、8 位帧序号、5 组 CH1/CH2 大端有符号 24 位、CRC-8/SMBUS；只向上位机发送 |
| 45671 | TCP | UTF-8 日志输出；发送以 `\n` 结尾的 ASCII 命令进行交互 |
| 45672 | UDP | 局域网发现：收到 `HEARTTHIRD_DISCOVER` 后回复 `HEARTTHIRD_ESP32S3` |

每个 TCP 端口同时服务一个客户端。网络发送与采集分任务，数据发送队列最多 32 帧；未连接或队列已满的样本会丢弃，并计入 `tcp_dropped`。`missed` 是 ADS DRDY 边沿间隔估计，两个计数含义不同。TCP 是字节流，接收端仍须按帧头和 CRC 解析，不应假设一次 `recv` 恰好返回 33 字节。日志队列最多 32 行，满时丢弃最旧日志；TCP 控制台重连后可使用 `status` 查询采集状态。

## 呼吸采集

上电默认 `breath off`、`rld off`：RLD 关闭、CH1/CH2 增益均为 6，呼吸载波关闭。向 TCP console 发送 `breath on`（末尾换行），采集任务会停止转换，校验 ADS1292R 身份和寄存器配置，再开启 CH1 呼吸调制/解调：CH1 增益 2、`RESP1=0xF6`（参考工程相位 0x0D）、`RESP2=0x03`（内部参考、32 kHz 载波）。CH1 原始采样是未经滤波的呼吸测量通道，CH2 仍为心电；33 字节数据格式不变。发送 `breath off` 恢复 CH1 增益 6 和关闭调制。`status` 查看实际启用状态，切换成功会输出 `verified` 日志；切换期间约有 1.2 秒采样暂停，采样计数重新开始。呼吸波是否可辨仍需在电极和模拟前端上实测。

## RLD 排查与切换

V1.0.1 默认关闭未经本板验证的 RLD；修复旧版 `status` 在采集正常时固定显示 `rld=on` 的问题。`status` 显示最近一次初始化读回校验成功的 `RLD_SENS`，故障时显示 `unavailable`，并非每次查询都读取硬件。

`rld on|off` 与 `breath on|off` 共用有界请求队列，仅由采集任务停止转换、重新初始化并校验全部配置后启动。RLD 切换保留呼吸、增益和采样率；呼吸切换保留 RLD。失败时恢复原配置，恢复失败则进入 FAULT。切换约暂停 1.2 秒并重置采样计数；命令的 `requested` 只表示入队，须等待 `verified` 日志确认生效。重启恢复默认关闭。

电池供电实测流程：烧录前接 USB，烧录后拔掉 USB，经 Wi-Fi 采集；保持电极、姿势和呼吸模式不变，按 `off → on → off` 比较 CH2 原始数据。每次切换等待稳定后使用相同长度数据，检查 45–55 Hz、95–105 Hz 幅值、削顶及丢样，不能以陷波后的曲线代替原始信号评估。`0xC0 ↔ 0xEC` 均保持 fMOD/4 斩波；历史 STM32 `0x00 ↔ 0xEC` 比较同时改变了斩波频率，不能单独归因于 RLD。

寄存器依据：[TI ADS1292R 数据手册第 57 页](https://www.ti.com/lit/ds/symlink/ads1292r.pdf)。如同条件下开启仍恶化，应继续检查 RL 线序、RLDOUT/RLDINV 的反馈阻容、参考电压及电极接触；本板电池供电对照结果见下文。

### 2026-09-24 电池供电对照结果

V1.0.1 经 Device Tool 烧录，用户确认移除 USB 后，经 Wi-Fi 按 `0xC0 → 0xEC → 0xC0` 实测；两通道增益 6、呼吸关闭、斩波 fMOD/4。每段约 26 秒，均收到 2597 帧 / 12985 对样本，取末尾 10000 对分析。切换已确认读回校验，分析窗口排除连接后前约 6 秒数据。三段序号丢帧、重复序号、CRC 错误、削顶均为 0，固件 `missed` 全程为 0。

| CH2 原始信号指标（ADC） | 关闭（首次） | 开启 | 关闭（复测） |
| --- | ---: | ---: | ---: |
| 45–55 Hz 频段 RMS | 24008 | 44044 | 25601 |
| 95–105 Hz 频段 RMS | 10092 | 1311 | 8923 |
| 45–55 Hz Hann 窗峰值幅度 | 33836 | 57034 | 30817 |

恢复关闭后，50 Hz 频段 RMS 比开启降低约 42%，与首次关闭结果接近；开启 RLD 的确加重本次 50 Hz 干扰，但减小 100 Hz 分量。当前保持 `rld=off / 0xC0`，重启默认也关闭。这是软件缓解措施，不代表模拟反馈电路已经修复，也不表示工频干扰完全消失。具体硬件原因仍需电路图或反馈网络测量确认。

分析使用去均值、Hann 窗、相同长度原始数据；频率轴按标称 500 SPS，内部时钟实测速率约 499 SPS，峰值显示约 50.1–50.15 Hz 不代表电网频率就是该值。主比较采用频段 RMS，减少单频点泄漏影响。原始数据：[NPZ](../develop/rld_measurement_20260924.npz)；定义、完整数值与校验：[JSON](../develop/rld_measurement_20260924.json)。

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
