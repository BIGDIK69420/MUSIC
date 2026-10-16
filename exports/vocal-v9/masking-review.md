# V9 masking and density review

No subjective audition is available. These measurements locate overlap and plausible intervention points; they do not establish perceptual muddiness, source anatomy, recording geometry, or room impulse response.

All inputs are 48 kHz stereo float32. Spectral analysis resamples to 16 kHz and uses a Hann 2048-point window and 512-sample hop. Activity is selected from the existing original-dry 40 ms RMS envelope, above −38 dBFS. Active frames are split into equal-count weak/medium/strong bins at −32.02 and −27.21 dBFS. Band power is stereo mean square, equivalent to Mid power + Side power. Analyzed-band percentages use only 60–7500 Hz, not total-spectrum energy.

## Main measurements

Positive Beat/Core means the accompaniment carries more power than the central/main vocal processing at that band. This is not a direct perceptual masking threshold.

|Band|Beat/Core, all active|Beat/Core, weak|FX/Core, all active|
|---|---:|---:|---:|
|125–200 Hz|−3.5 dB|−4.6 dB|−32.9 dB|
|200–350 Hz|−4.7|−4.0|−20.1|
|350–600 Hz|−4.4|−3.0|−12.6|
|600–1000 Hz|−2.4|+1.5|−9.3|
|1000–2000 Hz|−2.8|+0.5|−9.4|
|2000–4000 Hz|−3.3|−3.2|−10.1|
|4000–7500 Hz|−5.2|−5.4|−14.0|

The most competitive accompaniment region during weaker vocals is 600 Hz–2 kHz, not 200–350 Hz. The 160–190 s active segment also has Beat/Core +0.2 dB at 600–1000 Hz, while the 40–70 s segment is −1.0 dB and 100–130 s is −4.2 dB. Hence a fixed deep whole-song cut is not justified; activity-aware reduction is preferable.

The V8 main vocal has 39.3% of its analyzed-band power in 125–350 Hz across active frames, and 53.7% in the weak bin. This reflects pitch/content and compression as well as possible excess warmth; it is not inherently pathological. Its 350–1000 Hz total is 41.2%. Previous revisions already reduced that total relative to the original mixed voice, so another broad/deep scoop would risk hollowing it out.

The original accompaniment has 63.7% of its analyzed-band energy below 200 Hz during vocal activity; processed V7/V8 accompaniment has 60.0%. Those numbers include musical kick/bass and do not justify removing the bass. They do support looking at upper-bass sustain and limiter interaction separately from vocal EQ. No 60–125 Hz cut is recommended solely from these proportions.

## V8 added effects

600–1000 Hz active band level: doubles −38.2 dBFS, delay −50.1, plate −49.5. At 1–2 kHz: doubles −40.6, delay −52.4, plate −55.0. Thus the continuous pitch-shifted doubles dominate added midrange energy by roughly 11–14 dB over either delayed return. This is a better first intervention than deleting all musical tails. The core already contains the old rendered effects; newly doubling it also duplicates the existing coloration.

## Suggested first rendering, bounded and reversible

1. Lower V8 doubles 4–6 dB. Raise their high-pass to approximately 450–550 Hz (12 dB/oct). Keep phrase delays but reduce overall added returns as needed, rather than adding further de-essing or brighter shelves. This specifically tests whether continuous layered vowels/chorus are the remaining haze.
2. On accompaniment while singing, dynamic bell around 750–850 Hz, Q 0.75–0.9, maximum reduction 2–2.5 dB; attack 20–40 ms, release 120–200 ms. At most a gentle static 250–350 Hz cut of around 0.8–1.2 dB if the entire backing is still dense. Do not force reference-spectrum matching across different arrangements.
3. On main vocal, restrained 220–280 Hz reduction around 1–1.5 dB, preferably dynamic and no greater than 2 dB. Preserve low fundamentals and avoid further deep 500–900 Hz cuts without A/B feedback. This addresses low-mid prominence in weak phrases while retaining body.

Provide a version at the prior approximately −12.1 LUFS working level alongside any −11 LUFS deliverable so increased master limiting cannot masquerade as the only tonal change. For A/B, normalize the comparison excerpts, not merely sample peaks.

Scripts and full per-section measurements: `masking.py`, `masking.json`.
