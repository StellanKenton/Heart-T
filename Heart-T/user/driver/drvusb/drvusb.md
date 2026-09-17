---
port_files:
  - usbd_conf.c
  - usbd_conf.h
---
# USB CDC 驱动

| 文件 | 职责 |
| --- | --- |
| `drvusb.c/.h` | CDC 描述符、静态类存储、单包收发与回显 |
| `usbd_conf.c/.h` | STM32 HAL/PCD 绑定、PMA 分配、USB ISR 回调、协议栈配置 |

依赖：CubeMX `Core/Src/usb.c`、STM32F1 HAL、`Middlewares/ST/STM32_USB_Device_Library` 的 Core 和 CDC。
所有源码直接加入 `Heart-T/CMakeLists.txt`；不依赖 RTOS，不使用堆分配。

## 硬件与设备

- STM32F103C8，HSE 8 MHz → PLL 72 MHz → USB 48 MHz。
- PA11 = USB D−，PA12 = USB D+；板上需要 D+ 到 3.3 V 的外部 1.5 kΩ 上拉。
- 启动时 PA12 拉低 20 ms 再释放，确保固件复位后主机重新枚举；仅初始化阻塞，周期收发不等待。
- Full-speed CDC ACM 虚拟串口，产品名 `Heart-T USB CDC`，序列号来自 MCU 96 位 UID。
- 开发用途 VID/PID = `0483:5740`（ST CDC 示例值）；产品发布时应替换为获授权的 VID/PID。
- 波特率设置只存储和回读，不改变 USB 速度；不要求 DTR 才回显。

## API 与上下文

| API / 回调 | 上下文 | Contract |
| --- | --- | --- |
| `drvUsbInit()` | 主循环启动，单次 | `MX_USB_PCD_Init()` 后调用，注册 CDC、启动 PCD、最后启用 USB IRQ |
| `drvUsbEchoProcess()` | `communicationProcess()`，每 10 ms | 至多提交一包回显，或在发送完成后恢复接收；未配置、挂起和发送忙均正常返回 |
| CDC Init/DeInit/Control/Receive | USB ISR | 有界且非阻塞；发布接收长度，不在 ISR 中回显 |
| HAL PCD 回调 | USB ISR | 仅转发设备核心事件 |

返回值：`DRV_USB_OK` = 1；`DRV_USB_ERROR_STATE` = −10；`DRV_USB_ERROR_TRANSFER` = −11。

## 数据所有权

使用一个 64 字节静态缓冲区。OUT 收到包后不重新挂接接收，主机继续发送会得到 NAK 并重试；communication 提交原始字节到 IN，直到 CDC `TxState` 清零（包括整包后的 ZLP）才重新挂接 OUT。
因此支持包含 `00` 的二进制数据，不添加换行、不进行字符串转换。超过 64 字节的数据由 USB 主机拆包，按顺序逐包回显；不保留主机应用写调用的边界。
10 ms 调度和单包背压偏向低资源占用，连续 64 字节包的回显吞吐约为 3.2 KB/s。
任务访问 CDC 状态期间仅屏蔽 `USB_LP_CAN1_RX0_IRQn`，TIM2 和 DRDY 中断继续运行。
复位或取消配置清除旧会话；挂起保留当前包，恢复后继续。

PMA 分配：BTABLE `0x000..0x03F`，EP0 OUT `0x040..0x07F`，EP0 IN `0x080..0x0BF`，CDC IN `0x0C0..0x0FF`，CDC OUT `0x100..0x13F`，通知 IN `0x140..0x147`。

## 验证

通过 Device Tool Build 编译。烧录后将板载 USB 数据口连接电脑，打开新出现的 CDC 串口并关闭串口工具的本地回显。
分别发送文本、`00 FF 0D 0A`、63/64/65/128 字节和连续多包数据，确认接收内容与发送逐字节一致。
再检查 USB 拔插、固件复位、发送期间挂起/恢复，确认重新枚举及回显恢复。
仅编译和主机模拟无法证明实际硬件枚举与电气连接，仍需板上验收。
