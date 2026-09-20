---
port_files:
  - usbd_conf.c
  - usbd_conf.h
---
# USB CDC 驱动

| 文件 | 职责 |
| --- | --- |
| `drvusb.c/.h` | CDC 描述符、静态存储、采样对环形缓冲、异步数据帧发送 |
| `usbd_conf.c/.h` | STM32 HAL/PCD 绑定、PMA 分配、USB ISR 回调和配置 |

依赖：CubeMX USB PCD、STM32 HAL、ST USB Device Core/CDC；源码直接加入 CMake，不使用堆或 RTOS。
硬件：STM32F103C8，HSE 8 MHz → PLL 72 MHz → USB 48 MHz，PA11/PA12 为 D−/D+，D+ 需要外部 1.5 kΩ 上拉。
初始化前 D+ 拉低 100 ms 触发重新枚举；Full-speed CDC，VID/PID 为开发用 0483:5740。
波特率仅保存和回读，不控制 USB 速度；DTR 不作为发送条件。

## 协议

固定 33 字节，二进制、不添加换行：

| 偏移 | 长度 | 内容 |
| --- | --- | --- |
| 0 | 1 | 包头 FA |
| 1 | 1 | 包序号，0..255 循环 |
| 2..31 | 30 | 5 个采样时刻，每个时刻 CH1 三字节，随后 CH2 三字节 |
| 32 | 1 | CRC-8/SMBUS，覆盖偏移 1..31 |

通道值为有符号 24 位二进制补码，最高字节先发送。500 SPS 下每包覆盖 10 ms，正常数据量 3300 B/s。
CRC 多项式 0x07、初值 0、无反射、结果无异或；标准检查值 `123456789` → F4。
每采集 5 对生成一个包序号，独立于 USB 是否成功发送；缓冲溢出丢弃完整旧包时，后续序号出现跳变。
序号不检测 ADS 漏采，漏采查看 RTT 的 missed。序号模 256 有歧义，复位后上位机应重新建立基准。

## API 与所有权

| API | 上下文 | Contract |
| --- | --- | --- |
| `drvUsbDisconnect` | 启动，主循环 | USB PCD 初始化前调用 |
| `drvUsbInit` | 启动，主循环 | USB PCD 初始化后注册 CDC 并启用 IRQ |
| `drvUsbQueueSample` | sensorProcess，主循环 | 成功读取 ADS 后调用，同一时刻两通道复制到同一个槽 |
| `drvUsbStreamProcess` | communicationProcess，每 10 ms，主循环 | 至多提交一包，未配置、挂起、忙或不足 5 对时保留队列 |
| `drvUsbGetDroppedSamples` | 主循环 | 累计缓冲溢出丢弃的采样对数 |
| CDC 回调 | USB ISR | 收到主机数据后直接丢弃并重新挂接 OUT，不回显 |

40 槽环形缓冲可容纳约 80 ms 的采样，存储 240 字节通道数据和 40 字节序号。
主循环独占队列读写，ISR 不访问队列。满时丢弃最旧 5 对，保留组边界，RTT usb_dropped 累加 5。
USB RX 使用独立 64 字节缓冲，TX 使用独立 33 字节缓冲；发送完成前不修改 TX。
仅屏蔽 USB IRQ 保护类存储生命周期和 TxState，DRDY、TIM2 继续运行。
提交成功后才从队列移除 5 对；忙、未配置和提交失败都不出队。OK=1、STATE=−10、TRANSFER=−11。
提交成功表示 USB 栈已接管数据，不表示上位机已经解析；复位或拔插可能丢失正在传输的一包，无应用层确认重发。
挂起保留队列，但采样继续，超过容量会丢旧包。10 ms 调度发生延迟时不补跑，长期吞吐不足会造成溢出。

## 验证

编译使用 `py -3 develop/quick_deploy.py build`；烧录使用同一 Device Tool 的 flash。
上位机使用 [运行入口](../../../../HeartThirdCore/user/run.py)，不回传。
板上验证应检查持续接收、每秒约 100 包、序号连续、CRC 正确、CH1/CH2 原始码，以及 USB 忙、拔插和缓冲溢出。
原 develop/usb_selftest_result.json 是旧回显固件的历史测试，不能作为本协议的验收结果。
