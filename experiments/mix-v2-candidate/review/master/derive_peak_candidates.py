from pathlib import Path
import json
import numpy as np
from scipy import signal,ndimage
B=Path('/workspace/audio-v13');O=Path('/workspace/audio-v2-review-master');SR=48000
arr=lambda p:np.memmap(p,'float32','r').reshape(-1,2)
beat=arr(B/'beat.f32');prem=arr(B/'premaster.f32');master=arr(B/'master.f32');N=len(beat)
n=N//48*48
x=np.asarray(prem[:n]).reshape(-1,48,2)*10**(5.74/20);y=np.asarray(master[:n]).reshape(-1,48,2)
e=np.sum(x*x,(1,2));g=np.sum(x*y,(1,2))/np.maximum(e,1e-20);gr=-20*np.log10(np.clip(g,1e-6,1));gr[e/96<1e-5]=0
peaks=signal.find_peaks(gr,height=4.3,distance=150,prominence=.75)[0]
# Diagnostic LF detector uses causal lowpass solely for broad 50ms context, not audio processing.
low=signal.sosfilt(signal.butter(3,140,'lowpass',fs=SR,output='sos'),beat,axis=0)
power=np.mean(np.asarray(beat)**2,axis=1);lp=np.mean(low**2,axis=1)
voice=np.asarray(prem)-np.asarray(beat);vp=np.mean(voice**2,axis=1)
nearpeaks=[]
for i in peaks:
 n0=i*48;a=max(0,n0-480);b=min(N,n0+480)
 # Locate actual stereo sample peak within +/-10ms of known limiter pressure.
 pp=np.max(np.abs(beat[a:b]),axis=1);s=a+int(np.argmax(pp));peak=float(np.max(np.abs(beat[s])))
 def stats(w):
  aa=max(0,s-int(w*SR/2));bb=min(N,s+int(w*SR/2));bp=float(np.mean(power[aa:bb]));vv=float(np.mean(vp[aa:bb]));lf=float(np.mean(lp[aa:bb]));return {'beat_rms_dBFS':float(10*np.log10(max(bp,1e-20))),'beat_over_vocal_dB':float(10*np.log10(max(bp,1e-20)/max(vv,1e-20))),'lowpass140_fraction':lf/max(bp,1e-20)}
 st50=stats(.05);st20=stats(.02)
 # Prioritize clearly accompaniment-dominant, low-frequency-rich events.
 ok=st50['beat_over_vocal_dB']>=3 and st50['lowpass140_fraction']>=.3
 nearpeaks.append({'known_limiter_peak_time_s':float((i+.5)/1000),'limiter_estimated_GR_dB':float(gr[i]),'beat_actual_sample_peak_time_s':float(s/SR),'beat_actual_sample_peak_dBFS':float(20*np.log10(max(peak,1e-20))),'context50ms':st50,'context20ms':st20,'candidate':bool(ok),'suggested_maximum_dip_dB':float(min(.75,max(.35,.35+.20*(float(gr[i])-4.3)))) if ok else 0})
candidates=[p for p in nearpeaks if p['candidate']]
result={'method':'Candidate-only diagnostics, not audio processing. Existing full-mix 1ms approximate limiter-GR local peaks >=4.3dB, separation150ms, prominence0.75dB; locate actual beat sample peak +/-10ms. Gate on 50ms beat/vocal RMS >=3dB and causal 140Hz lowpass/full beat power >=0.3. Vocal estimated by exact premaster minus beat, without separated commercial content. LF fraction is context, not causal proof.','event_count_before_gates':len(nearpeaks),'event_count_after_gates':len(candidates),'candidates':candidates,'rejected_context_events':[p for p in nearpeaks if not p['candidate']],'recommended_design':{'linked_stereo':True,'finite_lookahead_ms':[5,8],'minimum_attack_smoothing_ms':[3,5],'short_hold_ms':[2,5],'release_ms':[35,60],'maximum_gain_dip_dB':.75,'not_a_hard_clipper':True,'control_resolution':'Use actual stereo sample-peak envelope or oversampled peak with finite lookahead; interpolate/smooth gain continuously. RMS only gates candidate context, never sets the transient location.','calibration':'These times are from V1. Recheck pressure and sample peak against the changed V2 premaster before finalizing. Gate can change if vocal level changes.'}}
(O/'peak-candidates.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))
