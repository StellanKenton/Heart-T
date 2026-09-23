# 离线 ECG 波形查看器

读取 CSV 的 `ch2_raw`，显示 CH2 原始波形与经 0.5–40 Hz 带通、50.07 Hz 陷波后的 CH4 波形。若 CSV 有 `elapsed_ms` 列，则用它作为横轴时间；否则按 500 Hz 生成时间。滤波和心率计算仍按 500 Hz 采样率进行。

## 运行

在仓库根目录执行：

```powershell
py -3 OfflineWaveHandle/main.py D:\data\heart_raw.csv
py -3 OfflineWaveHandle/main.py D:\data\heart_raw.csv --save D:\data\waveform.png
```

省略 CSV 路径时会打开文件选择框。依赖 `numpy`、`scipy`、`matplotlib`。界面可平移和缩放显示范围、标记两个测量点，并导出仅含 `ch2_raw` 和 `ch4` 的 CSV。

| 文件 | 职责 |
| --- | --- |
| `main.py` | 解析参数、选择文件、启动加载和绘图 |
| `data.py` | 读取 CH2、滤波生成 CH4、检测 R 峰、计算心率与测量值、导出数据、按视口抽样 |
| `waveform.py` | 显示两条波形及交互控件，只从数据对象取值 |

绘图按视口宽度抽样并保留局部极值，拖动时合并短时间内的连续刷新，以减少大文件操作时的卡顿。
