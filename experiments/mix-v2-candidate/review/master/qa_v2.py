from pathlib import Path
import json
import numpy as np
from scipy import signal
O=Path('/workspace/audio-v2-review-master');A=Path('/workspace/audio-v13');B=Path('/workspace/audio-v2-candidate');SR=48000
arr=lambda p:np.memmap(p,'float32','r').reshape(-1,2)
audio={v:{n:arr(p/(n+'.f32')) for n in ['beat','premaster','master']} for v,p in [('V1',A),('V2',B)]}
N=len(audio['V1']['beat']);dip=np.memmap(B/'beat_dip_dB.f32','float32','r');assert len(dip)==N
cfg=json.load(open(B/'validation.json'));events=json.load(open(O/'peak-candidates.json'))['candidates'];newdrive=cfg['master']['passes'][-1]['gain_dB'];drives={'V1':5.74,'V2':newdrive}
def dBpower(x):return float(10*np.log10(max(float(x),1e-30)))
def energy(x):return float(np.mean(np.asarray(x,dtype='float64')**2))
def quant(x):return {str(p):float(np.percentile(x,p)) for p in [50,90,95,99,99.9,100]}
def stereo(x):
 m=x.mean(1);s=(x[:,0]-x[:,1])*.5;return {'side_mid_dB':dBpower(energy(s)/energy(m)),'mono_fold_energy_dB':dBpower(energy(m)/(energy(m)+energy(s))),'LR_correlation':float(np.corrcoef(x[::8].T)[0,1])}
def crest(x):return float(20*np.log10(max(float(np.max(abs(x))),1e-20))-dBpower(energy(x)))
# Validate exact scalar-source transformation, which also establishes sample alignment.
gain=10**(-np.asarray(dip)/20);expected=audio['V1']['beat']*gain[:,None]
identity_error=float(np.max(abs(expected-audio['V2']['beat'])));assert identity_error<2e-7
changes=(dip>1e-7);unaffected=~changes
stereo_cross=float(np.max(abs(audio['V2']['beat'][:,0]*audio['V1']['beat'][:,1]-audio['V2']['beat'][:,1]*audio['V1']['beat'][:,0])))
GR={};valid={}
for v in ['V1','V2']:
 p=audio[v]['premaster'];m=audio[v]['master'];n=len(p)//48*48
 x=np.asarray(p[:n]).reshape(-1,48,2)*10**(drives[v]/20);y=np.asarray(m[:n]).reshape(-1,48,2)
 e=np.sum(x*x,(1,2));g=np.sum(x*y,(1,2))/np.maximum(e,1e-20);GR[v]=-20*np.log10(np.clip(g,1e-6,1));valid[v]=e/96>1e-5
K=len(GR['V1']);t=(np.arange(K)+.5)/1000;normal=np.ones(K,dtype=bool);eventrows=[]
for ev in events:
 c=ev['beat_actual_sample_peak_time_s'];z=(t>=c-.030)&(t<=c+.150);normal[(t>=c-.050)&(t<=c+.500)]=False
 row={'center_s':c,'dip_dB':ev['suggested_maximum_dip_dB'],'window_s':[c-.030,c+.150]}
 for v in ['V1','V2']:row[v+'_GR_max_dB']=float(np.max(GR[v][z]));row[v+'_GR_mean_dB']=float(np.mean(GR[v][z]))
 row['GR_max_change_dB']=row['V2_GR_max_dB']-row['V1_GR_max_dB'];row['GR_mean_change_dB']=row['V2_GR_mean_dB']-row['V1_GR_mean_dB']
 for ms in [20,50,200]:
  a=max(0,int((c-ms/2000)*SR));b=min(N,int((c+ms/2000)*SR))
  for stem in ['beat','master']:
   row[f'{stem}_{ms}ms_crest_change_dB']=crest(audio['V2'][stem][a:b])-crest(audio['V1'][stem][a:b])
 eventrows.append(row)
active=normal&valid['V1']&valid['V2'];normal_stats={v:{'GR_dB_percentiles':quant(GR[v][active]),'percent_over3dB':float(100*np.mean(GR[v][active]>3))} for v in ['V1','V2']}
# 40ms normal-window crest preserving source timing, exact excluded event window.
normal40=active[:len(active)//40*40].reshape(-1,40).all(1);crest40={}
for v in ['V1','V2']:
 x=np.asarray(audio[v]['master'][:len(normal40)*1920]).reshape(-1,1920,2);p=np.max(abs(x),(1,2));r=np.sqrt(np.mean(x*x,(1,2)));crest40[v]=20*np.log10(np.maximum(p,1e-20)/np.maximum(r,1e-20))
normal_crest_delta=crest40['V2'][normal40]-crest40['V1'][normal40]
# Frequency/mono checks use only narrow relevant low bands; gain-match masters by measured 0.01LU.
bandchanges={}
for stem in ['beat','master']:
 bandchanges[stem]={}
 for lo,hi in [(25,70),(70,140),(140,300)]:
  sos=signal.butter(3,[lo,hi],'bandpass',fs=SR,output='sos');en={}
  for v in ['V1','V2']:
   x=signal.sosfilt(sos,audio[v][stem],axis=0)
   if stem=='master' and v=='V2':x*=10**(.01/20)
   en[v]=energy(x)
  bandchanges[stem][f'{lo}-{hi}']=dBpower(en['V2']/en['V1'])
# Gain modulation: bounded, smooth envelope. This is a signal check, not an audibility guarantee.
d=np.diff(np.asarray(dip,dtype='float64'));gstep=np.diff(np.asarray(gain,dtype='float64'))
f,P=signal.welch(np.asarray(dip),fs=SR,nperseg=65536)
modtotal=np.sum(P[f>0]);modhigh=np.sum(P[f>500]);mod1k=np.sum(P[f>1000])
residual=audio['V2']['beat']-audio['V1']['beat'];resdb=dBpower(energy(residual)/energy(audio['V1']['beat']))
st={v:{stem:stereo(audio[v][stem]) for stem in ['beat','master']} for v in ['V1','V2']}
aggregate={'events':len(events),'max_GR_delta_percentiles_dB':quant(np.array([e['GR_max_change_dB'] for e in eventrows])),'mean_GR_delta_percentiles_dB':quant(np.array([e['GR_mean_change_dB'] for e in eventrows])),'event_max_GR_improved_more_than005dB':sum(e['GR_max_change_dB']<-.05 for e in eventrows),'event_max_GR_worsened_more_than005dB':sum(e['GR_max_change_dB']>.05 for e in eventrows),'beat_50ms_crest_change_percentiles_dB':quant(np.array([e['beat_50ms_crest_change_dB'] for e in eventrows])),'master_50ms_crest_change_percentiles_dB':quant(np.array([e['master_50ms_crest_change_dB'] for e in eventrows]))}
result={'scope':'Independent verification of new sparse accompaniment peak repairs and their master interaction. No new rendering and no subjective audition. Limiter gain is approximate 1ms least-squares and includes resampling. V2 includes separate vocal changes, so final-master differences are not uniquely attributable to beat repair.','source_transform':{'frames':N,'exact_scalar_gain_max_error':identity_error,'unaffected_samples_max_error':float(np.max(abs(audio['V2']['beat'][unaffected]-audio['V1']['beat'][unaffected]))),'stereo_cross_product_max_error':stereo_cross,'finite':bool(all(np.isfinite(audio[v][s]).all() for v in audio for s in audio[v])),'sample_alignment':'Source verified as identical sample positions times known common stereo gain; no added delay.'},'gain_envelope':{'maximum_dip_dB':float(np.max(dip)),'above_01dB_seconds':float(np.sum(dip>.1)/SR),'largest_sample_step_dB':float(np.max(abs(d))),'largest_sample_gain_step_linear':float(np.max(abs(gstep))),'envelope_power_above500Hz_relative_dB':dBpower(modhigh/modtotal),'envelope_power_above1kHz_relative_dB':dBpower(mod1k/modtotal),'beat_residual_relative_energy_dB':resdb},'paired_events':eventrows,'aggregate':aggregate,'normal_segments':normal_stats,'normal_40ms_crest_change_dB_percentiles':quant(normal_crest_delta),'long_term_band_energy_change_dB':bandchanges,'stereo':st,'master_drive_dB':drives,'master_LUFS':{'V1':-11.55,'V2':cfg['master']['WAV_LUFS']},'interpretation':'The unchanged or slightly lower master drive cannot compensate away the source repair. Small modulation of the selected beat peaks is intentional; smooth common gain avoids channel decorrelation or frequency-split phase shifts. Whether microdynamics sound preferable still requires audition.'}
assert aggregate['event_max_GR_worsened_more_than005dB']==0
assert abs(normal_stats['V2']['GR_dB_percentiles']['95']-normal_stats['V1']['GR_dB_percentiles']['95'])<.05
assert all(abs(v)<.15 for v in bandchanges['beat'].values())
assert float(np.max(abs(d)))<.01
result['status']='PASS'
(O/'qa_v2.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='paired_events'},indent=2))
