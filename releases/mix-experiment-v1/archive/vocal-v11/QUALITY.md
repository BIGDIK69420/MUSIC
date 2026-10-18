# Independent V11 tonal/dynamic/width verification

Checked completed `/workspace/audio-v11/core.f32` and `vocal.f32` against the tuned V7 source, V9, and the existing reference-vocal estimates. No production audio was modified, no reference separation rerun, and no subjective audition is claimed. This audit deliberately does not use V10's residue reduction as the goal: the user rejected that direction.

## Source meaning

V11 returns to `/workspace/audio-reference/vocal_final.f32`. CORE means the V11 lead with **the newly added V11 backing, delay and reverberation disabled**. It still contains the original wet tuning, dynamics, tonal treatment and previously printed ambience inherited from V7. It is not raw dry, anechoic audio or a recovered studio stem.

The reviewed V11 tonal chain includes an 80 Hz high-pass, 300 Hz +0.4 dB, shallow selective 900 Hz / 4 kHz dynamic treatment, 10 kHz +0.7 dB shelf, and the quiet selected-vowel harmonic residual. Measured results below incorporate all these stages rather than predicting their effect from settings alone.

## Tonal shape retained

Whole-song Mid spectra use a **shared original-dry activity mask** (> −38 dBFS in 40 ms windows). Each source is normalized to its own active 300 Hz–5 kHz energy. This cancels simple overall gain differences; it does not estimate subjective loudness or identify the original singer's EQ.

| Active Mid band | V11 CORE minus V7 | Full V11 minus V7 | Full V11 minus V9 |
|---|---:|---:|---:|
| 80–150 Hz | −0.51 dB | −0.60 dB | +0.40 dB |
| 150–300 Hz | +0.03 dB | −0.05 dB | +0.89 dB |
| 300–600 Hz | +0.20 dB | +0.14 dB | +0.49 dB |
| 600–1200 Hz | −0.16 dB | −0.12 dB | −0.32 dB |
| 1.2–2.5 kHz | −0.07 dB | +0.01 dB | −0.28 dB |
| 2.5–5 kHz | −0.32 dB | −0.32 dB | −0.64 dB |
| 5–10 kHz | −0.01 dB | −0.08 dB | −0.36 dB |
| 10–16 kHz | +0.43 dB | +0.35 dB | +0.07 dB |

There is **no V10-like several-dB reduction in the upper spectral bands relative to the accepted V7 source**. The added layers also leave the average central tonal shape close to CORE. Relative to V9 the low body is somewhat fuller because V11 starts from V7 and does not retain V9's additional low-mid cleanup; this follows the new beautification direction, not a claim that more low-mid energy always sounds better.

## Dynamics preserved

Using the same shared dry activity mask:

| Version | Active 40 ms P90−P10 | Active 40 ms P95−P50 |
|---|---:|---:|
| V7 | 4.21 dB | 2.04 dB |
| V9 | 4.40 dB | 2.01 dB |
| V11 CORE | 4.16 dB | 2.08 dB |
| Full V11 | 4.21 dB | 2.11 dB |

The lead finishing and added production do not cause an additional broad collapse in these active-frame dynamics. This does not mean V7's existing printed compression has been removed; it remains baked into the source. Short-window statistics are not a substitute for listening to articulation and phrasing.

## Width and reference comparison

For the two reference comparisons, the existing analysis method is reused: each 30-second excerpt's active threshold is its own P95 frame energy minus 20 dB; spectra normalize to 300 Hz–5 kHz. These self-adaptive excerpt statistics differ from the whole-song shared-mask statistics above and must not be mixed numerically.

| Version / excerpt | Side/Mid 40–70 s | Side/Mid 100–130 s | LR correlation 40–70 s / 100–130 s |
|---|---:|---:|---:|
| Reference estimate | −9.88 dB | −9.38 dB | 0.814 / 0.794 |
| V7 | −20.84 dB | −20.64 dB | 0.984 / 0.983 |
| V9 | −18.75 dB | −17.99 dB | 0.974 / 0.969 |
| V11 CORE | −20.72 dB | −20.60 dB | 0.983 / 0.983 |
| Full V11 | −17.73 dB | −15.23 dB | 0.967 / 0.942 |

V11 adds measurable side content while keeping a stronger central emphasis than the estimated reference. Its different width between passages is consistent with the phrase/vowel-dependent arrangement. Matching the reference's Side/Mid number exactly would not establish a better or more similar result because it includes different backing performances, production and possible separation remnants.

Final V11 minus reference estimate, same excerpt method:

| Mid band | 40–70 s | 100–130 s |
|---|---:|---:|
| 300–600 Hz | +1.66 dB | −0.17 dB |
| 600–1200 Hz | −1.67 dB | +0.21 dB |
| 1.2–2.5 kHz | −0.24 dB | −0.22 dB |
| 2.5–5 kHz | +0.72 dB | +0.23 dB |
| 5–10 kHz | +1.86 dB | −1.29 dB |
| 10–16 kHz | −1.50 dB | −2.38 dB |

Upper-mid presence remains close under this approximate comparison; there is no evidence here requiring another large presence lift. The air-band difference remains modest and is not a reliable exact EQ target because of sibilance, breath and possible percussion leakage in the separated reference. Low-body 150–300 Hz remains about +7.69/+6.71 dB relative to the estimated reference, but singer pitch, vowels and separation differ; that large difference should not trigger another large low-mid scoop after the user's new instruction.

## Sample integrity and mono compatibility

- All four checked stems have 10,285,140 frames at 48 kHz: 214.27375 seconds.
- All samples are finite; no samples reach digital full scale.
- CORE sample peak: −4.36 dBFS. Complete V11 vocal sample peak: −3.85 dBFS. These are stem sample peaks, not mastered true-peak measurements.
- Complete V11 vocal full-file mono-fold energy change: −0.095 dB; CORE: −0.040 dB. No gross global mono cancellation is indicated. Local synthetic-backing coloration still requires audition.
- Complete V11 full-file Side/Mid: −16.55 dB, compared with V7 −20.42 dB and V9 −18.10 dB.

## Supported conclusion

The delivered design retains V7's central voice and existing tuning, with small tonal finishing and increased, phrase-dependent side production. The measured tone/dynamics do **not** repeat the large darkening or source replacement of V10. These checks establish the intended technical direction and basic integrity; they cannot establish beauty, professional record quality, disappearance of phone-like character, or identity-level similarity to the reference singer.

Reproduce with `python /workspace/audio-v11-review/quality.py`. Detailed measurements: `QUALITY.json`. The reference estimates are analysis inputs only and are not part of the audio output.
