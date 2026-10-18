# Independent final V10 vocal checks

Measured final `/workspace/audio-rebuild/{vocal,core}.f32` against the original dry, original wet and V9 `clean_vocal.f32`. These are the rerendered files with the limited presence adjustment adopted into the main version: 3300 Hz/Q0.9 +3.2 dB and 6500 Hz shelf +3 dB, increments of only +2/+1 dB over the first V10 draft. No additional alternate listening version is proposed or delivered here. The earlier draft measurements are preserved in `initial-tone/` for reproducibility.

This audit is not listening and cannot verify perceived improvement. It does not inspect the master, which was still rendering during these vocal checks.

## Comparable method

All versions use the same masks defined by the original dry: active 40 ms RMS > −38 dBFS; quiet < −55 dBFS, within 8–188 s, with roughly ±250 ms clearance from frames exceeding −45 dBFS. Spectra use 4096-sample Hann STFT, hop 2048 at 48 kHz. Quiet mask covers 567 frames / 24.192 s. Quiet-to-active is the band-energy ratio within each file, so differing output gain is canceled. Active spectra are normalized to that file's active 80 Hz–16 kHz band energy. These are diagnostic energy comparisons, not inferred EQ settings.

## Retained residues

| Band | V9 quiet/active | V10 core quiet/active | V10 with effects quiet/active | V10 versus V9 |
|---|---:|---:|---:|---:|
| 150–300 Hz | −27.48 dB | −39.97 dB | −39.85 dB | −12.37 dB |
| 300–600 Hz | −24.12 dB | −43.26 dB | −38.32 dB | −14.21 dB |
| 600–1200 Hz | −24.87 dB | −42.39 dB | −36.63 dB | −11.76 dB |
| 1200–2500 Hz | −23.95 dB | −32.20 dB | −30.63 dB | −6.68 dB |

The core retains much of the dry file's quiet-versus-active separation. The new return adds measurable between-phrase sound, especially 300 Hz–1.2 kHz, but remains substantially below V9 by this measure. The limited presence adjustment preserves the reduction found in the initial V10 draft. These results support that the rendering took a different source path and reduced the previously printed residue. They do not distinguish room noise, vocal breath, reverb and delay by themselves.

## Dynamics and sample integrity

- Active 40 ms RMS P90−P10: raw dry 13.55 dB; old wet 4.42 dB; V9 4.40 dB; V10 core 5.70 dB; V10 5.71 dB.
- V10 core peak −5.48 dBFS; complete vocal peak −5.43 dBFS. All five sources finite and zero samples at/above full scale.
- All five files have 10,285,140 frames / 214.27375 s.
- Core is mono; complete V10 vocal mono-fold energy change is only −0.003 dB. No large global stereo cancellation detected.

## Tonal tradeoff

Even after the limited presence adjustment, final V10 is **not brighter than V9** across its upper spectrum. With active band normalization, V10 versus V9 is:

- 150–300 Hz −0.12 dB; 300–600 Hz +0.60 dB; 600–1200 Hz +1.08 dB.
- 1.2–2.5 kHz +0.01 dB; 2.5–5 kHz −2.81 dB; 5–10 kHz −4.54 dB; 10–16 kHz −6.42 dB.
- Summed 150–1200 Hz relative to 80 Hz–16 kHz is −0.92 dB for V10 versus −1.46 dB for V9, a +0.53 dB increase in this normalized measure. It would be incorrect to claim all singing low-mid density was reduced.

This reflects abandoning the earlier printed enhancement and EQ chain. Relative to the original dry, V10 core has approximately +4.66 dB in 2.5–5 kHz, +4.39 dB in 5–10 kHz, +4.63 dB in 10–16 kHz, and +3.87 dB in 16–20 kHz after normalization. There is no broad high-frequency loss relative to dry evident from these band totals, but tonal naturalness and fine restoration artifacts still require audition.

The 20–75 Hz band is about 19.8 dB above V9 in relative terms, but still only −38.38 dB relative to active 80 Hz–16 kHz energy (less than 0.02%). This is a very small absolute component and should not be presented as a new major rumble problem.

## Reference-direction check and final decision

Reused the already separated reference excerpts and the exact `audio-v8-reference/compare.py` metric function; **no new model inference and no audio alteration by this review**. Metrics normalize Mid spectrum to 300 Hz–5 kHz, select each excerpt's frames within 20 dB of its own P95, and separately test the more energetic half. Results are in `final_quality_reference.json`; reproduce with `final_quality_reference.py`. A null Side/Mid value for a purely mono file represents zero side energy, not an invalid audio signal.

| Final V10 minus estimated reference vocal | 40–70 s | 100–130 s | Stronger half, range |
|---|---:|---:|---:|
| 1.2–2.5 kHz | +0.10 dB | −0.44 dB | +0.10 to −0.69 dB |
| 2.5–5 kHz | −1.39 dB | −3.63 dB | −1.36 to −4.38 dB |
| 5–10 kHz | −2.93 dB | −6.10 dB | −3.73 to −7.94 dB |
| 10–16 kHz | −9.71 dB | −9.43 dB | −11.03 to −11.12 dB |

The earlier V10 draft had a 2.5–5 kHz shortfall of −2.99/−5.17 dB under this metric; the final limited adjustment reduces that gap without matching the full reference spectrum. V9's 2.5–5 kHz is +1.38/+0.65 dB relative to the same reference; its 5–10 kHz is +2.27/−1.03 dB. Thus abandoning the old wet chain changes not only air-band enhancement but also presence. The final version addresses part of that presence risk with a bounded adjustment while preserving the new source path and lower between-phrase residue. No old printed wet signal has to be mixed back in, and no full spectral matching is justified.

**Reference limits:** This is an estimated separated stem, not an artist-provided solo. Different songs and different singers are not phoneme/pitch matched. The model can retain music and lose vocal effects; identity processing of an isolated user voice does not prove clean separation on the commercial mix. Earlier high-band checks found 33% of reference 40–70 s air-band energy concentrated in only 6.7% low-mid-quiet frames, consistent with sibilance/air and possible percussion leakage. Therefore the roughly 9–10 dB air difference is particularly unsuitable as an EQ target. Even the more repeatable presence difference supplies a direction for a limited adjustment, not a verified required correction.

## Supported conclusion

The strongest claim supported is **less between-phrase low/mid residue and a fresh vocal source path, with slightly more active dynamics**. The main version now incorporates a measured, limited presence correction. Do not claim that phone-like quality or muddiness is eliminated. Final V10 still differs substantially from V9 in tone; whether that tradeoff resolves the complaint remains the listening question. Comparing both complete mix and solo voice at matched loudness is appropriate.

Reproduce: `python /workspace/audio-v10-review/final_quality.py` and `python /workspace/audio-v10-review/final_quality_reference.py`. Detailed data: `final_quality.json`, `final_quality_reference.json`; normalized active spectra: `final_quality_spectra.npz`.
