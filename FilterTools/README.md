# 双通道频谱分析工具

`spectrum_analysis.py` 读取 CSV 中同步采集的两个通道，计算单边 Hann 窗 FFT 幅度谱和 50% 重叠的 Welch 功率谱密度（PSD）。默认读取 `ch1_raw`、`ch2_raw`，并从 `elapsed_ms` 推算采样率；若无有效时间列则使用 500 Hz。

## 安装与运行

```powershell
py -3 -m pip install -r FilterTools/requirements.txt
py -3 FilterTools/spectrum_analysis.py D:\data\heart_raw.csv
```

不提供 CSV 路径时会打开文件选择框：

```powershell
py -3 FilterTools/spectrum_analysis.py
```

常用参数：

```powershell
py -3 FilterTools/spectrum_analysis.py data.csv --sample-rate 500 --max-frequency 150 --show
py -3 FilterTools/spectrum_analysis.py data.csv --channels channel_a channel_b --segment-length 1024
```

默认在输入文件旁创建 `<CSV文件名>_spectrum` 目录，输出：

- `fft.csv`：频率与两通道 FFT 幅度。
- `psd.csv`：频率与两通道 PSD，单位为输入单位平方每 Hz。
- `spectrum.png`：FFT 与 PSD 对比图。

完整参数可通过 `py -3 FilterTools/spectrum_analysis.py --help` 查看。

## 单通道工频峰值分析

`peak.py` 使用 Welch 功率谱密度分析 CSV 中的 `ch1`–`ch4`，默认在
45–55 Hz 范围内查找并打印最大峰值，同时绘制 PSD 曲线。通道字段映射与
`fft.py` 相同：`ch1`、`ch2` 分别读取 `ch1_raw`、`ch2_raw`，`ch3`、`ch4`
读取同名字段。

```powershell
py -3 FilterTools/peak.py D:\data\heart_raw.csv
```

不提供 CSV 路径或通道时会依次打开选择框。也可以通过参数直接选择通道；默认采样率为
500 Hz：

```powershell
py -3 FilterTools/peak.py data.csv --channel ch4 --sample-rate 500 --min-frequency 45 --max-frequency 55
```
