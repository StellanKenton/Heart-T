# SPI2 驱动

| 信号 | MCU 引脚 |
| --- | --- |
| CS，低有效 | PB12，GPIO 输出 |
| SCLK | PB13，SPI2 |
| MISO / ADS DOUT | PB14，SPI2 |
| MOSI / ADS DIN | PB15，SPI2 |

硬件配置在 `Core/Src/spi.c`、`Core/Src/gpio.c` 和 `Heart-T.ioc` 中保持一致。
模式 1（CPOL=0、CPHA=1）、8 位、MSB first、软件 NSS、PCLK1 / 256。
当前 PCLK1=36 MHz，SCLK 约 140.625 kHz；低于内部 512 kHz 时钟对应的寄存器访问上限。
字节时间约 57 µs，满足多字节命令的 4 tCLK 解码时间；事务结束再保持 CS 低至少 10 µs。

| API | 契约 |
| --- | --- |
| `drvSpiInit` | 在 MX_DMA_Init、MX_SPI2_Init 后调用；校验配置，启用 DWT 周期计数 |
| `drvSpiTransfer` | TX、RX 均非空、长度非零、缓冲区不重叠；整次事务只拉低一次 CS；20 ms 超时；失败中止 SPI 并释放 CS |
| `drvSpiDelayUs` | init 后调用，硬件忙等待；只用于短微秒延时，参数不超过 1000 µs |

返回 `1` 成功；`-10` 参数错误，`-11` 状态错误，`-12` 超时，`-13` 传输错误。
API 只允许主循环上下文；SPI2 由主循环独占，不带互斥，不允许 ISR 调用。
当前采集帧短小，使用阻塞收发；保留 CubeMX DMA 初始化，未启用异步 DMA 收发。
