# 混音实验 V1

**正式 V1 = 用户确认成功的旧实验 V13。** 这是版本确立与经验归档，所有音频均原样复制，没有重新处理、编码、调整音量或添加音频标签。文件 SHA-256 与 V13 一致。

用户确认：“v13太棒了，作为混音实验成功的V1吧。把至今为止的经验，总结打包，并让v13成为第一版”。确认日期：2026-10-18（Asia/Singapore）。

## 先从这里开始

- [V1 完整成品 MP3](MUSIC_MIX_EXPERIMENT_V1.mp3) · [24-bit WAV](MUSIC_MIX_EXPERIMENT_V1.wav)
- [V1 成品与经验包 ZIP](MUSIC_MIX_EXPERIMENT_V1_PACKAGE.zip)：包含完整 WAV、MP3、等响对照、下列经验文档、历史技术记录与校验工具。
- [历次实验与经验](HISTORY_AND_LESSONS.md)：目标如何演变、哪些方向得到认可、哪些尝试失败、哪些原因仍未确定。
- [有效处理链与复现指南](CHAIN_AND_REPRODUCTION.md)：最终谱系、具体参数、分轨用法及重建条件。
- [后续工作交接](CONTINUE_FROM_V1.md)：以后从这版继续时应先读的简明记录。

此处“成功”指用户已确认这一版达到本次实验的预期；并非声学原因已全部证实或获得了独立唱片质量认证。

## 成品与分轨

| 文件 | 用途 |
|---|---|
| `MUSIC_MIX_EXPERIMENT_V1.mp3` | 320 kbps 完整成品 |
| `MUSIC_MIX_EXPERIMENT_V1.wav` | 完整成品，48 kHz / 24-bit / stereo |
| `MUSIC_MIX_EXPERIMENT_V1_VOCAL.wav` | 母带前完整人声 |
| `MUSIC_MIX_EXPERIMENT_V1_VOCAL_CORE.wav` | 人声主体，含早先打印的处理与部分空间 |
| `MUSIC_MIX_EXPERIMENT_V1_VOCAL_FX.wav` | 可单独调节的衬层、延迟与混响 |
| `MUSIC_MIX_EXPERIMENT_V1_BEAT.wav` | 与这版人声配套的伴奏 |
| `MUSIC_V12_TO_MIX_EXPERIMENT_V1_COMPARE.mp3` | 旧 V12 与正式 V1 的等响对照 |

四个独立 WAV 分轨在[正式 V1 在线目录](https://github.com/BIGDIK69420/MUSIC/tree/mix-experiment-v1/releases/mix-experiment-v1)单独下载。ZIP 包含主成品 WAV / MP3 和全部经验资料，**不包含这四个分轨**，以保持为一个可直接下载的文件。

所有完整音频均为 214.27375 秒，从 0:00 对齐。Ableton 中关闭 Warp，分轨推子设为 0 dB：`CORE + FX ≈ VOCAL`；`VOCAL + BEAT` 得到母带前混音。独立 PCM24 导出存在极小量化误差。请使用本版 BEAT；完整成品另含母带增益与限幅。不要把 VOCAL 与 CORE 重复相加。CORE 不是未经处理的干声。

## 等响对照顺序

| 对照文件时间 | 内容 |
|---|---|
| 0–24.25 秒 | 旧 V12 混音 |
| 24.75–49 秒 | 正式 V1 混音（旧 V13） |
| 49.5–59.5 秒 | 旧 V12 独奏 |
| 60–70 秒 | 正式 V1 独奏（旧 V13） |

混音组各约 −16 LUFS，独奏组各约 −20 LUFS。这个对照没有经过重新渲染，仅改变文件名。它记录 V1 确立前的最后一次实验，不代表正式 V1 与未来 V2 的比较。

## 封存数据

- V1 完整 WAV：−11.55 LUFS / −1.38 dBTP；MP3：−11.56 LUFS / −0.98 dBTP。数值来自此前 V13 的导出测量，本次音频字节不变。
- `release.json` 记录正式版本、用户确认、原 V13 提交及全部音频的旧名称与哈希映射。
- `manifest.json` 记录本目录各交付内容的哈希及是否包含在 ZIP 内。解压后可运行 `python verify_release.py`，仅需 Python 标准库。
- `archive/` 原样保存现有旧实验 V3–V13 的 91 份非音频文档、代码、分析及验证数据。历史文档中的结论和反馈属于当时状态，后续修正见本包总结。早于 V3 的交付没有完整仓库记录，不补造参数或文件。
- 历史代码部分依赖原工作区的音频、模型或分析结果。经验包可供阅读、核验与继续使用成品；并非能从原始干声一键重建所有历史版本的独立工程。

后续以正式 V1 为固定试听基线，下一次获认可的正式改版记为 **V2**。旧实验编号保留用于追溯，V1 音频及其哈希保持不变。
