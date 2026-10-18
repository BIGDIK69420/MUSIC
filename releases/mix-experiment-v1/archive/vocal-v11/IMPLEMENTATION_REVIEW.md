# V11 implementation and output audit

The rendering code and exported samples were inspected independently. No subjective listening or artistic-quality judgment is claimed.

## Outcome

No blocking implementation or output-integrity error found. The main vocal path uses the existing V7 tuned vocal. The V10 pitch-analysis archive is used only to select sustained voiced spans; it is not an audio source. The beat is the V9 cleaned accompaniment. Reference-song audio does not enter the render.

## Implementation

- Harmonic color: 4x polyphase upsampling, nonlinear tanh with a small DC bias, polyphase anti-alias downsampling, subtraction of an input-proportional least-squares component, band-pass filtering, and sustained-vowel gating. This is a quiet nonlinear residual, not a raw dry-vocal parallel layer.
- Doubles: the source is gated before Rubber Band pitch shifting; -6/+7 cents affect only the backing voices. Both mono outputs contain exactly 10,285,140 samples. The 31/49 ms delays preserve output length. Band-pass filtering limits low-frequency overlap. The support gate does not perfectly identify phonemes, but the implementation follows the intended continuous-voicing control.
- Echo: only 11 selected phrase-ending sends excite the repeats. Each phrase alternates one rhythmic interval (444.44 or 666.67 ms at 135 BPM), with progressively quieter/darker repeats and alternating pan. The lead does not pass through these delays. Repeats and longer tails are ducked while the lead is active.
- CORE plus newly added FX equals VOCAL, up to floating-point rounding. CORE still contains the printed effects inherited from V7; it is not a dry vocal.
- Premaster equals VOCAL plus the V9 beat exactly in float32. No accidental doubling of the full demo or reference audio is present.
- Master limiter operates at 192 kHz and returns to 48 kHz. Four target iterations completed; the final 5.9 dB drive is the drive used for the approximate gain-reduction statistics. The hypothetical fifth-pass bookkeeping boundary was not reached.

## Independent measurements

- All raw production layers and all delivered WAV files have finite samples, correct duration (214.27375 s), and no samples at or beyond 0 dBFS.
- All four WAV exports are 48 kHz stereo, 24-bit PCM; quantization deviation from their float sources is less than 1.19e-7.
- The MP3 decodes to the same 10,285,140 stereo frames as the WAV. No end truncation was found; the last 20 ms master peak is approximately -79 dBFS.
- Independent 4x oversampled peak estimates: WAV -1.368 dBFS, decoded MP3 -1.016 dBFS. These agree closely with the renderer's -1.38/-1.02 dBTP values. The renderer's loudness scan reports -11.52 LUFS for both; that full loudness scan was not redundantly repeated.
- Master mono-fold energy change is -0.278 dB, and left/right correlation is 0.876. These do not indicate broad stereo cancellation.
- CORE + FX versus VOCAL maximum sample error is 5.96e-8 (-169.08 dBFS RMS error). VOCAL + beat versus premaster has zero sample error.

## Sustained-vowel and cancellation spot checks

Defining off-gate support as voiced control <=0.001 and more than 100 ms away from any control frame above that threshold leaves 139.025 s. The double layer in those intervals is -131.62 dBFS RMS, 98.93 dB quieter than its selected-vowel RMS; its off-gate peak is -89.50 dBFS. Harmonic-color samples outside the gate have a peak below -110 dBFS. This confirms that the additional vowel layers are negligible in distant unselected material. Deliberate echo/reverb tails are separate and are not expected to disappear at the vowel boundary.

Adding FX changes mono 250–1200 Hz energy by +0.063 dB across active singing and +0.155 dB across sustained vowels. There is no systematic reduction in that band. Local interference still exists, as expected with synthetic delayed doubles: active 40 ms windows have a fifth-percentile change of -0.487 dB, 1.55% fall below -1 dB, and the worst single window is -3.20 dB at 86.12 s. It would be inaccurate to say there is absolutely no comb filtering; these measurements show that it is not a persistent broad low-mid loss.

Detailed records: qa_v11.json and qa_vowel_and_sum.json. Scripts: qa_v11.py and qa_vowel_and_sum.py.
