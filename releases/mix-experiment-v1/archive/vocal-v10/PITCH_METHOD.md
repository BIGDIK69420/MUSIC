# Original vocal pitch following (V10 experiment)

This process estimates the user's own dry and already mixed vocal fundamental frequency. It does not use the reference recording as audio or as a voice model. It does not impose a new musical scale.

Analysis: pyworld DIO + StoneMask at 16 kHz, 10 ms hop, 65–700 Hz. Pitch estimation only; WORLD does not synthesize any delivered waveform. Trusted pitch frames require both estimates, raw RMS > 0.006, raw periodicity > 0.65 and mixed periodicity > 0.55. A correction greater than 120 cents is not followed. The final map is median/Gaussian smoothed, confidence-faded, and bounded to ±100 cents. Uncertain sections return toward zero correction.

Original dry → mixed comparison over 92.83 seconds of trusted paired frames: median absolute difference 23.94 cents, 90th percentile 61.91 cents. These differences are appreciable, so using the dry source unchanged would lose some of its existing tuning.

Rendering uses FFmpeg's Rubber Band waveform pitch shifter, formant preserved, smooth transients, soft detector, laminar phase, consistency pitch quality. The pitch command timestamps are delayed by 75 ms because a pilot found the filter's buffered processing otherwise applies parameter changes early. This is a control-timing correction, not an audio time shift.

20-second pilot (60–80 s) after that correction: median target pitch error ~7 cents versus ~24 cents before; 90th percentile ~28 cents versus ~60 cents. Not every frame is reliably tracked. An envelope correlation test gave 0.963 and a coarse peak at +5 ms; this is not proof of sample-exact identity.

## Usage

`python /workspace/audio-v10-pitch/render_pitch.py --input INPUT --input-channels 2 --output OUTPUT.f32`

Input may be WAV/MP3/etc, or a 48 kHz raw float32 file ending `.f32`. For raw files, `--input-channels 1` (default) or `2` must match. Output is 48 kHz mono float32, same duration, with the pitch map generated from original raw and mixed files. Add `--pilot` to render only source seconds 60–80; omit for full source. Default command timing compensation is `--delay 0.075`.

Example for the restoration agent's output:
`python /workspace/audio-v10-pitch/render_pitch.py --input /workspace/audio-v10-restoration/raw_full_restore_0.35.f32 --input-channels 2 --output /workspace/audio-v10-pitch/restored_tuned_mono.f32`

Do not run two renders simultaneously: intermediate command and source files share names. No subjective audition is available; pitch metrics and timing checks do not establish absence of audible pitch-shifting artifacts.

## Full source validation

On the full original raw source, the unrestricted DIO tracker after rendering occasionally jumps an octave (~1% upper tail). The applied pitch factor is bounded to less than one semitone (observed maximum 88.63 cents), so the aggregate DIO cent RMS is not treated as a reliable rendering-error statistic.

An independent normalized autocorrelation check searches lags within ±15% of original frequency, with parabolic lag refinement and paired periodicity > 0.7. Across 85.77 seconds, target pitch absolute error falls from 20.45 to 4.41 cents median; 51.80 to 16.98 cents at the 90th percentile; 60.92 to 24.73 cents at the 95th percentile; cent RMS falls 30.48 to 12.27. This supports following the existing pitch course in confidently voiced frames, not exact replication of the original autotuner.

20-second envelope comparisons at 10–30, 60–80, 120–140, and 180–200 seconds have correlations 0.979, 0.962, 0.961, and 0.962. Best envelope lags at 1 ms grid are +1, +3, +1, and −2 ms. There is no observed fixed whole-file delay to compensate.
