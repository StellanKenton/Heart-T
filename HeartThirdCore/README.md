# 上位机接收程序



`receiver.py` 通过 USB CDC 接收、校验和解析双通道数据，只接收，不向设备回传。
`test_receiver.py` 验证 CRC、半包/粘包、通道解码、序号回绕、丢包与损坏帧恢复。

当前目录原有 core/domain/hmi/user/build 为空，接收入口暂设在本目录。



```powershell

py -3 -m pip install pyserial

py -3 HeartThirdCore/receiver.py COM25

py -3 HeartThirdCore/receiver.py COM25 --all

```



将 COM25 替换为实际端口。默认每秒显示累计包数、采样对数、估计丢包数、CRC 错误数和最新通道值；`--all` 显示全部采样对。

数据为有符号 24 位 ADC 原始码，每通道 500 SPS；当前增益 6、参考 2.42 V，电压换算为 `code * 2.42 / (6 * 8388608)` V。



协议见 [USB 驱动文档](../Heart-T/user/driver/drvusb/drvusb.md)。解析支持半包、粘包和 CRC 失败后的重新对齐。

序号按模 256 比较，连续丢失 256 包无法识别；重复序号单独计为 sequence_errors。

设备复位、USB 断开或更换会话后关闭并重启接收程序，重新建立序号基准；自动重连暂未实现。

包序号检测传输和缓冲溢出丢包，ADS 漏采需查看 RTT 的 missed；CRC-8 存在碰撞可能。


协议测试：`py -3 -m unittest discover -s HeartThirdCore -p test_receiver.py`。
