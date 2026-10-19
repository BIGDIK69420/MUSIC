from pathlib import Path
import json
import numpy as np
from scipy import signal, ndimage

O=Path('/workspace/audio-v2-review-vocal');SR=48000;H=1920
def read(path):return np.memmap(path,mode='r',dtype=np.float32).reshape(-1,2)
def db(x):return 10*np.log10(np.maximum(x,1e-20))
def frames(x):
 n=len(x)//H*H
 m=x[:n].mean(1).reshape(-1,H)
 return np.mean(m*m,axis=1),np.max(abs(m),axis=1)**2
def stats(x):
 m=x.mean(1);s=(x[:,0]-x[:,1])/2
 p,pk=frames(x);a=db(p)>np.percentile(db(p),95)-20
 band={}
 f,t,z=signal.stft(m,SR,nperseg=4096,noverlap=2048)
 pw=abs(z)**2;active=db(pw.sum(0))>np.percentile(db(pw.sum(0)),95)-20
 av=pw[:,active].mean(1);den=av[(f>=300)&(f<5000)].sum()
 for lo,hi in [(80,150),(150,300),(300,600),(600,1200),(1200,2500),(2500,5000),(5000,8000),(8000,12000),(12000,16000)]:
  band[f'{lo}-{hi}']=float(db(av[(f>=lo)&(f<hi)].sum()/den))
 return {'duration':len(x)/SR,'active40ms_p90_p10':float(np.percentile(db(p[a]),90)-np.percentile(db(p[a]),10)),
 'active40ms_p95_p50':float(np.percentile(db(p[a]),95)-np.percentile(db(p[a]),50)),
 '40ms_crest_dB_p50_p95':np.percentile(db(pk[a]/p[a]),[50,95]).tolist(),
 'Side_Mid_total_dB':float(db(np.mean(s*s)/np.mean(m*m))), 'band_relative_300_5000_dB':band}
out={};c=read('/workspace/audio-v13/core_mix.f32');v=read('/workspace/audio-v13/vocal.f32')
for a,b in [(40,70),(100,130)]:
 out[f'V1_core_{a}_{b}']=stats(c[a*SR:b*SR])
 out[f'V1_vocal_{a}_{b}']=stats(v[a*SR:b*SR])
 out[f'ref_estimate_{a}_{b}']=stats(read(f'/workspace/audio-v8-reference/reference_vocal_{a}_{b}.f32'))
ctrl=np.load('/workspace/audio-v13/controls.npz');t=np.arange(len(c)//H)*.04+.02
active=np.interp(t,ctrl['times'],ctrl['activity'])>.8
voiced=np.interp(t,ctrl['times'],ctrl['voiced'])>.7
dry=np.interp(t,ctrl['times'],ctrl['drydb']);entry=np.interp(t,ctrl['times'],ctrl['entry'])>.4
p,pk=frames(c);weak=active&voiced&(dry<np.percentile(dry[active&voiced],40))
strong=active&voiced&(dry>np.percentile(dry[active&voiced],65))
masks={'active':active,'voiced':active&voiced,'weak_voiced':weak,'strong_voiced':strong,'phrase_entry':entry,'gap':~active}
out['states']={}
for name,mask in masks.items():
 out['states'][name]={'seconds':float(mask.sum()*.04),'core_level_percentiles_10_50_90':np.percentile(db(p[mask]),[10,50,90]).tolist(),'core_40ms_crest_p50_p95':np.percentile(db(pk[mask]/p[mask]),[50,95]).tolist()}
for name in ['doubles','echo','shallow','deep']:
 x=read(f'/workspace/audio-v13/{name}.f32');q,_=frames(x)
 for maskname,mask in masks.items():out['states'][maskname][name+'_to_core_dB']=float(db(q[mask].sum()/p[mask].sum()))
for path,name in [(c,'core'),(v,'vocal')]:
 m=path.mean(1);s=(path[:,0]-path[:,1])/2;n=len(m)//H*H
 pm=np.mean(m[:n].reshape(-1,H)**2,axis=1);ps=np.mean(s[:n].reshape(-1,H)**2,axis=1)
 bands={}
 for lo,hi in [(150,400),(400,1200),(1200,5000),(5000,10000)]:
  z=signal.sosfilt(signal.butter(2,[lo,hi],fs=SR,btype='bandpass',output='sos'),m)
  bands[f'{lo}-{hi}']=np.mean(z[:n].reshape(-1,H)**2,axis=1)
 for maskname,mask in masks.items():
  out['states'][maskname][name+'_side_mid_dB']=float(db(ps[mask].sum()/pm[mask].sum()))
  out['states'][maskname][name+'_band_ratios_dB']={k:float(db(z[mask].sum()/pm[mask].sum())) for k,z in bands.items()}
# Relative HF excess is an indicator, not a phoneme classification.
m=c.mean(1);n=len(m)//H*H
def bandpower(lo,hi):
 z=signal.sosfilt(signal.butter(2,[lo,hi],fs=SR,btype='bandpass',output='sos'),m)
 return np.mean(z[:n].reshape(-1,H)**2,axis=1)
hf=bandpower(5000,9500);body=bandpower(700,4000);ratio=db(hf/body)
out['HF_indicator']={'active_ratio_p50_p90_p95_p99':np.percentile(ratio[active],[50,90,95,99]).tolist(),
'strong_voiced_ratio_p50_p90_p95':np.percentile(ratio[strong],[50,90,95]).tolist(),
'active_seconds_HF_ratio_above_minus3dB':float(np.sum(active&(ratio>-3))*.04)}
(O/'analysis.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
