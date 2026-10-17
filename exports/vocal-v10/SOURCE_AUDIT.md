# V10 source-path audit

This is a waveform/spectrum audit, not an audition. It does not verify perceived cleanliness or identify recording hardware/room/anatomy from the files.

## Findings that change the next rendering decision

1. **There is no evidence of telephone-style 3–4 kHz hard bandwidth loss in the original dry recording.** During frames with dry RMS > −38 dBFS, the dry has measured 5–10 kHz energy at −21.88 dB relative to its total 80 Hz–16 kHz energy, and 10–16 kHz at −25.21 dB. Even 16–20 kHz is present (−33.76 dB by the same denominator). These values are not a tonal ideal and are not proof that all high-frequency energy is useful vocal signal. They do show that “phone-like” should not be interpreted as literal telephone bandwidth. The beat's >16 kHz rolloff is much stronger; that alone does not establish the user's perceived dirtiness.

2. **The old wet print contains much more low/mid-frequency energy between phrases, relative to its own singing level.** Select dry 40 ms RMS < −55 dBFS, time 8–188 s, excluding nearby > −45 dBFS frames with a roughly ±0.25 s margin: 567 STFT frames, 24.192 s. In these same frames, quiet/active energy ratios are:

| Band | Dry quiet/active | Original wet quiet/active | Difference |
|---|---:|---:|---:|
| 150–300 Hz | −39.10 dB | −27.04 dB | +12.06 dB |
| 300–600 Hz | −44.05 dB | −25.66 dB | +18.40 dB |
| 600–1200 Hz | −45.52 dB | −29.95 dB | +15.57 dB |
| 1200–2500 Hz | −35.90 dB | −29.50 dB | +6.40 dB |

These are per-file ratios, avoiding simple output-gain differences. They include reverb/delay residues, breath/noise and any quiet voice. They do NOT prove microphone room reflections. They support testing a fresh dry-source path because restoring this contrast with EQ alone is unlikely to isolate unwanted residues from the wanted vowel at the same frequencies.

3. **Quiet dry intervals contain a recurrent ~100 Hz narrow tone.** One-second Welch windows resolve the coarse STFT 105.47 Hz bin to approximately 100 Hz. Summed 99–101 Hz energy is about −63.3 dBFS at 1–5 s; −64.4 dBFS at 9–10.7 s; −60.3 dBFS at 29.2–30.8 s; −62.0 dBFS at 105.7–107.5 s; −64.3 dBFS at 195–205 s. It is weaker in at least one interval (−76.3 dBFS at 14.3–15.7 s). This is compatible with a hum-like component; it does not identify mains coupling or microphone/PC source. It is too low to call the principal cause of whole-song dirtiness. A narrow, shallow reduction is defensible; a deep broad 100 Hz cut is not.

4. **The wet chain changes weak and strong phrases very differently.** For dry RMS −45…−35 dBFS, wet 150 Hz–1.2 kHz gains are around +12 dB; for >−25 dBFS, they are around −0.8 to +1.4 dB. Meanwhile 10–16 kHz is +12.8 dB even in strong phrases. This is consistent with substantial leveling and spectral enhancement; it is not a transfer-function measurement because the vocal is tuned, nonlinear and reverberant. Avoid trying to invert this with fixed EQ.

5. **The previously identified very narrow wet peaks remain a reason not to recycle the wet print automatically.** At 41.7908, 47.1127, 96.4876, 135.8340 s, wet 5–11-sample events reach approximately −1.7…−2.9 dBFS against ~−24 dBFS local RMS. Dry corresponding windows lack such high peaks. The cause and audibility remain unverified. Earlier masters already limited these; rediscovering them is not a new fix for V9.

## Minimal independent dry-source chain to test

This is a separate rebuild, never mix the independently tuned old wet and raw dry together. Their timing, pitch and phase differ.

- Mono center from dry. Preserve timing. HP 65–75 Hz, 12 dB/oct. Optional peaking 100 Hz, Q 20–25, −4 to −6 dB to reduce the measured narrow tone; no broad deep low-frequency removal.
- Avoid blanket spectral denoising unless clearly beneficial. Background is already tens of dB below singing. If gating is needed, gentle downward expansion below approximately −52…−55 dBFS, ratio 1.5:1, range ≤10 dB, 5 ms attack, 150–220 ms release, 10 ms lookahead. Avoid abruptly removing breaths/endings.
- Level active phrases only: ~0.5–1 s RMS/phrase gain with boosts capped +6 dB and cuts around −4 to −6 dB; do not apply the boost into gaps. Aim for active-frame P90−P10 roughly 7–10 dB as a diagnostic alternative to the old wet's 4.4 dB, not a universal vocal target.
- One main compressor: 2.5–3:1, 6 dB knee, attack 12–20 ms, release 80–120 ms. Choose threshold for typical ~2–4 dB and high-percentile ~5 dB reduction; measure, do not assume from threshold. Peak catch only rare events after this, not another constant leveler.
- Restrained tone shaping after leveling: wide 250–450 Hz reduction only around 1–2 dB when heavy; modest presence around 1.8–3 kHz +1–2 dB as needed, high shelf ≥8 kHz only +0…+1.5 dB initially. Do not use exciter/saturation in this diagnostic route.
- One split-band de-esser, approximately 5–9 kHz, ceiling 2–3 dB reduction, consonant-selective. The raw recording does not need the previous multiple de-ess/enhance/de-ess loop.
- Effects from this new source only. First render a dry-forward core. Then one filtered/delayed, ducked return: 45–60 ms pre-delay, 0.65–0.9 s tail, high-pass roughly 400–500 Hz, low-pass 6–7 kHz, very low send (~−26 to −30 dB RMS relative to active voice), duck a further 4–6 dB under singing. No continuous microshift layer in the diagnostic version.
- Preserve the existing arrangement/beat; only modest voice-triggered masking control. Compare at matched integrated loudness and inspect vocal level as well as master loudness.

**Pitch limitation:** Rebuilding from the supplied raw dry discards the tuning printed into the old wet. Preserve the user's performance/pitch trajectory unless a separately verified tuning route is available. Do not describe the raw rebuilt vocal as retaining the previous Auto-Tune. An intentional alternate with more natural tuning is a meaningful tradeoff if explained.

## Reproduction

`python /workspace/audio-v10-review/source_audit.py`

Produces `source_audit.json`. `noise_resolved.json` separately stores the 1 Hz Welch measurements used for the 100 Hz finding. Existing wet transient measurements are in `/workspace/audio-review/wet-transients.json`.
