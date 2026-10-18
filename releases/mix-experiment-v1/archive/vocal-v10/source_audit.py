import json
from pathlib import Path
import numpy as np
from scipy import signal,ndimage
P=Path('/workspace/audio-analysis');O=Path('/workspace/audio-v10-review'); sr=48000
Db=lambda x: float(10*np.log10(max(float(x),1e-30)))
dbamp=lambda x:float(20*np.log10(max(float(x),1e-15)))
x={k:np.memmap(P/(k+'.f32'),dtype=np.float32,mode='r').reshape(-1,2).mean(axis=1) for k in ['dry','mixed','beat']}
S={k:dict(np.load(P/(k+'_spectrum.npz'))) for k in x}
f=S['dry']['f'];t=S['dry']['t'];p=S['dry']['power'];winr=np.interp(t,np.arange(len(np.load(P/'dry_rms.npy')))*.04+.02,np.load(P/'dry_rms.npy'));rdb=20*np.log10(np.maximum(winr,1e-15))
active=rdb>-38
quiet=(rdb<-55)&(t>8)&(t<188)
# Quiet excludes speech vicinity within 250 ms so short phone gestures less likely.
quiet=quiet&(~ndimage.maximum_filter1d((rdb>-45).astype(int),size=13).astype(bool))
bands=[(20,75),(75,150),(150,300),(300,600),(600,1200),(1200,2500),(2500,5000),(5000,10000),(10000,16000),(16000,20000),(20000,24000)]
R={'active_frames':int(active.sum()),'quiet_frames':int(quiet.sum()),'quiet_time_seconds':float(quiet.sum()*2048/sr),'spectral_bands':{},'quiet_spans':[],'narrow_noise_peaks':{},'time_segments':{}}
for k in x:
 pp=S[k]['power'];ref=np.mean(pp[(f>=80)&(f<16000)][:,active].sum(axis=0));rows=[]
 for lo,hi in bands:
  e=pp[(f>=lo)&(f<hi)].sum(axis=0);rows.append({'Hz':[lo,hi],'active_relative_to_80_16k_dB':Db(np.mean(e[active])/ref),'quiet_relative_to_active_dB':Db(np.mean(e[quiet])/np.mean(e[active]))})
 R['spectral_bands'][k]=rows
 # Spectrum steep drop above 3-5k? RMS amount 4-12k vs 0.3-3k etc
 R['time_segments'][k]=[]
 for a,b in [(1,5),(7,15),(35,40),(70,80),(185,193),(195,205)]:
  u=x[k][int(a*sr):int(b*sr)];seg={'seconds':[a,b],'rms_dBFS':dbamp(np.sqrt(np.mean(u*u)))}
  for lo,hi in [(20,75),(75,150),(150,600),(600,3000),(3000,10000),(10000,20000)]:
   so=signal.butter(3,[lo,hi],fs=sr,btype='band',output='sos');v=signal.sosfilt(so,u);seg[str(lo)+'_'+str(hi)]=dbamp(np.sqrt(np.mean(v*v)))
  R['time_segments'][k].append(seg)
# Noise peaks using aggregated non speech frames, log spectrum local prominence.
for k in ['dry','mixed']:
 q=S[k]['power'][:,quiet].mean(axis=1); floor=ndimage.median_filter(q,size=25); prom=10*np.log10(np.maximum(q,1e-30)/np.maximum(floor,1e-30)); ids,_=signal.find_peaks(prom,height=6,distance=2);ids=[i for i in ids if 50<f[i]<15000];ids=sorted(ids,key=lambda i:q[i],reverse=True)[:15]
 R['narrow_noise_peaks'][k]=[{'Hz':float(f[i]),'above_local_median_dB':float(prom[i]),'relative_80_16k_noise_dB':Db(q[i]/q[(f>=80)&(f<16000)].sum())} for i in ids]
# runs of quiet frames
idx=np.flatnonzero(quiet);groups=np.split(idx,np.where(np.diff(idx)>1)[0]+1)
R['quiet_spans']=[{'start':float(t[g[0]]),'end':float(t[g[-1]]),'duration':float((len(g)*2048)/sr)} for g in groups if len(g)>=3]
# Gain-dependent spectral tilt: no precise transfer claimed due retuning/effects.
R['gain_dependent_change']=[]
for lo,hi in [(-45,-35),(-35,-25),(-25,0)]:
 sel=(rdb>=lo)&(rdb<hi);row={'dry_rms_dBFS':[lo,hi],'frames':int(sel.sum()),'band_wet_minus_dry_dB':{}}
 for a,b in [(75,150),(150,300),(300,600),(600,1200),(1200,2500),(2500,5000),(5000,10000),(10000,16000)]:
  mask=(f>=a)&(f<b);pd=S['dry']['power'][mask][:,sel].sum(axis=0);pw=S['mixed']['power'][mask][:,sel].sum(axis=0);row['band_wet_minus_dry_dB'][str(a)+'_'+str(b)]=Db(pw.mean()/pd.mean())
 R['gain_dependent_change'].append(row)
(O/'source_audit.json').write_text(json.dumps(R,indent=2))
print(json.dumps(R,indent=2))
