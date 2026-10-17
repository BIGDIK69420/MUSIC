# V10 去混响候选（专用模型）

已实际运行公开的 **UVR-DeEcho-DeReverb** 神经网络模型，元数据标签 `No Reverb`，不是用人声／伴奏分离器冒充去混响。CPU 推理，原音频没有发送到外部服务。模型 SHA-256、来源、架构与参数见 `provenance.json`；运行环境位于本目录 `venv`，网络源码位于 `uvr`（上游提交 `a5f88453bfb2b38b05a965bcf67727243e0cbf19`）。

## 20 秒可行性对照

输入：原始 `dry.f32` 与旧 `mixed.f32` 的 100–120 秒。两者均 48 kHz、双声道。模型在 44.1 kHz 多频带谱上估计保留遮罩，保留输入相位；恢复时使用 `原信号 − 强度 × 模型预测残留`，让模型频带范围外的原信号继续保留。没有额外 EQ、压缩、饱和、归一化或调音。

| 输入与强度 | 全段 RMS 变化 | 活跃 40 ms 帧变化中位数 | 较安静帧变化中位数 | 互相关时移 |
|---|---:|---:|---:|---:|
| dry 35% | −0.0007 dB | 约 0 dB | −0.96 dB | 0 样本 |
| dry 65% | −0.0011 dB | 约 0 dB | −1.76 dB | 0 样本 |
| 旧 wet 35% | −0.23 dB | −0.20 dB | −1.93 dB | 0 样本 |
| 旧 wet 65% | −0.41 dB | −0.36 dB | −3.70 dB | 0 样本 |

此表“活跃/较安静”按各段 40 ms 单声道 RMS 划分，阈值为该段最高 RMS 的 8%，不是分离出的真混响标签。详细频段、帧分布与峰值见 `assessment.json`。

在原 dry 的这个片段，唱句各主要频段变化均低于 0.001 dB。模型几乎只处理较弱尾部；**不能宣传它已清除 raw 的根本盒子感，也不能由此断言录音房间没有问题。** 更可靠的主路线是丢弃已打印旧处理、从 dry 重建；本模型只是保守的辅助手段。

## 可用文件

- `raw_restore_0.35.f32` / `raw_restore_35_100_120.wav`：100–120 秒原 dry 35% 处理样例。
- `wet_restore_0.65.f32` / `wet_restore_65_100_120.wav`：100–120 秒旧 wet 65% 处理样例。
- `raw_full_restore_0.35.f32`：全曲原 dry 保守版，供重调音／重混音使用。
- `raw_full_restore_0.65.f32`、`raw_full_restore_1.00.f32`：全曲较强版，仅作为对照备选。
- `raw_full_estimated_reverb.f32`：模型预测残留，不能视为真实房间脉冲响应或真实独立混响轨。

全部 f32 均为交错双声道 float32、48 kHz。全曲目标长度与原文件相同：10,285,140 帧，214.27375 秒。`full_validation.json` 记录最终帧数、峰值、有限性、多个时间段的互相关时移与帧电平影响；使用前以此确认完整输出。

## 运行

```
/workspace/audio-v10-restoration/venv/bin/python /workspace/audio-v10-restoration/test_model.py
/workspace/audio-v10-restoration/venv/bin/python /workspace/audio-v10-restoration/full_raw.py
python /workspace/audio-v10-restoration/validate_full.py
```

神经网络预测可能误认气声、尾音和辅音。20 秒样例未见整体频宽或声体明显削薄的数值证据；这不能替代实际试听。没有进行主观听感验证。
