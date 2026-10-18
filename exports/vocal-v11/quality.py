from pathlib import Path
import json
import numpy as np
from scipy import signal
exec(Path('/workspace/audio-v8-reference/compare.py').read_text().split('out={}')[0])
O=Path('/workspace/audio-v11-review');FS=48000
paths={'V7':Path('/workspace/audio-reference/vocal_final.f32'),'V9':Path('/workspace/audio-clean/clean_vocal.f32'),'V11_CORE':Path('/workspace/audio-v11/core.f32'),'V11':Path('/workspace/audio-v11/vocal.f32')}
N=paths['V7'].stat().st_size//8
for p in paths.values():
 assert p.exists() and p.stat().st_size==N*8,(str(p),'missing/incomplete')
dryr=np.load('/workspace/audio-analysis/dry_rms.npy');active40=dryr>10**(-38/20);tt=(np.arange(len(dryr))+.5)*.04
f0,t0,z0=signal.stft(np.zeros(N,dtype='float32'),FS,nperseg=4096,noverlap=2048,boundary=None)
mask=np.interp(t0,tt,dryr)>10**(-38/20)
rows={};spectra={};excerpt={};db=lambda x:float(10*np.log10(max(float(x),1e-30)))
for name,path in paths.items():
 x=np.memmap(path,dtype='float32',mode='r').reshape(-1,2);m=x.mean(1);s=(x[:,0]-x[:,1])/2
 n=len(dryr);r=np.sqrt(np.mean(m[:n*1920].reshape(n,1920)**2,1));rdb=20*np.log10(np.maximum(r,1e-15))
 _,_,zm=signal.stft(m,FS,nperseg=4096,noverlap=2048,boundary=None);p=abs(zm)**2
 _,_,zs=signal.stft(s,FS,nperseg=4096,noverlap=2048,boundary=None);ps=abs(zs)**2
 active_m=p[:,mask].mean(1);active_s=ps[:,mask].mean(1);norm=active_m[(f0>=300)&(f0<5000)].sum()
 spec={f'{lo}-{hi}':db(active_m[(f0>=lo)&(f0<hi)].sum()/norm) for lo,hi in bands}
 width={f'{lo}-{hi}':db(active_s[(f0>=lo)&(f0<hi)].sum()/active_m[(f0>=lo)&(f0<hi)].sum()) for lo,hi in bands}
 spectra[name]=spec
 rows[name]={'path':str(path),'duration_seconds':len(x)/FS,'finite':bool(np.isfinite(x).all()),'peak_dBFS':float(20*np.log10(abs(x).max())),'samples_ge_fullscale':int((abs(x)>=1).sum()),'same_mask_active40ms_P90_P10_dB':float(np.percentile(rdb[active40],90)-np.percentile(rdb[active40],10)),'same_mask_active40ms_P95_P50_dB':float(np.percentile(rdb[active40],95)-np.percentile(rdb[active40],50)),'active_mid_band_dB_relative_300_5000':spec,'active_side_mid_by_band':width,'full_file_side_mid_dB':db(np.mean(s*s)/np.mean(m*m)),'full_file_mono_fold_energy_dB':db(np.mean(m*m)/np.mean(x*x)),'LR_correlation':float(np.corrcoef(x[::8].T)[0,1])}
 for a,b in [(40,70),(100,130)]:
  excerpt[name+f'_{a}_{b}']=metrics(np.asarray(x[a*FS:b*FS]))
ref=json.loads(Path('/workspace/audio-v8-reference/vocal_comparison.json').read_text());compare={}
for a,b in [(40,70),(100,130)]:
 key=f'{a}_{b}';rf=ref['reference_estimated_vocal_'+key];excerpt['REFERENCE_'+key]=rf
 for name in paths:
  r=excerpt[name+'_'+key];compare[name+'_minus_REFERENCE_'+key]={k:float(v-rf['mid_band_dB_relative_300_5000'][k]) for k,v in r['mid_band_dB_relative_300_5000'].items()}
deltas={}
for name in ['V11_CORE','V11']:
 for other in ['V7','V9']:
  deltas[name+'_minus_'+other]={k:float(v-spectra[other][k]) for k,v in spectra[name].items()}
res={'same_mask':'Original dry 40ms RMS > −38 dBFS; all-band normalization uses active Mid 300Hz–5kHz. Reference excerpts use previous self-adaptive P95−20dB frame criterion and Mid 300Hz–5kHz normalization, so they are separate comparisons.','files':rows,'whole_file_active_deltas':deltas,'excerpts':excerpt,'reference_deltas':compare,'core_meaning':'CORE disables newly added V11 backing/delay/reverb only. It still contains V7 printed pitch, dynamics, EQ and prior ambience; it is not original raw or anechoic vocal.','limits':'No audition; energy, dynamics and width measurements cannot establish beauty, artist similarity or perceptual clarity. Reference model estimate is not a true artist solo stem.'}
def clean(o):
 if isinstance(o,dict):return {k:clean(v) for k,v in o.items()}
 if isinstance(o,list):return [clean(v) for v in o]
 if isinstance(o,float) and not np.isfinite(o):return None
 return o
(O/'QUALITY.json').write_text(json.dumps(clean(res),indent=2,allow_nan=False))
print(json.dumps({'whole_file_active_deltas':deltas,'dynamics':{k:{a:b for a,b in r.items() if 'P90' in a or 'P95' in a or 'side_mid_dB' in a or 'mono_fold' in a or 'peak' in a} for k,r in rows.items()},'reference_deltas':compare},indent=2))
