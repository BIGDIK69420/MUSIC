"""Independent, same-mask vocal checks; no perceptual quality inference."""
from pathlib import Path
import json
import numpy as np
from scipy import signal,ndimage
O=Path('/workspace/audio-v10-review');P=Path('/workspace/audio-analysis');R=Path('/workspace/audio-rebuild');sr=48000
paths={'dry':P/'dry.f32','original_wet':P/'mixed.f32','V9':Path('/workspace/audio-clean/clean_vocal.f32'),'V10_core':R/'core.f32','V10':R/'vocal.f32'}
Db=lambda x:float(10*np.log10(max(float(x),1e-30)))
da=lambda x:float(20*np.log10(max(float(x),1e-15)))
dryr=np.load(P/'dry_rms.npy');nt=len(dryr);r40db=20*np.log10(np.maximum(dryr,1e-15));active40=r40db>-38
S=np.load(P/'dry_spectrum.npz');f=S['f'];t=S['t'];rd=np.interp(t,np.arange(nt)*.04+.02,dryr);rdb=20*np.log10(np.maximum(rd,1e-15));active=rdb>-38
quiet=(rdb<-55)&(t>8)&(t<188);quiet&=~ndimage.maximum_filter1d((rdb>-45).astype(int),size=13).astype(bool)
bands=[(20,75),(75,150),(150,300),(300,600),(600,1200),(1200,2500),(2500,5000),(5000,10000),(10000,16000),(16000,20000)]
res={'mask':{'active_threshold_dBFS':-38,'quiet_threshold_dBFS':-55,'quiet_frames':int(quiet.sum()),'quiet_total_sec':float(quiet.sum()*2048/sr),'quiet_exclusion_near_gt_minus45_sec':.25},'files':{},'deltas':{}}
allbp={};spec={}
for k,path in paths.items():
 x=np.memmap(path,dtype='float32',mode='r').reshape(-1,2);m=x.mean(1);r=np.sqrt(np.mean(m[:nt*1920].reshape(nt,1920)**2,axis=1));db=20*np.log10(np.maximum(r,1e-15));a=r[active40]
 ff,tt,z=signal.stft(m,sr,nperseg=4096,noverlap=2048,boundary=None);pp=abs(z)**2
 assert np.allclose(f,ff) and np.allclose(t,tt)
 ref=pp[(f>=80)&(f<16000)][:,active].sum(axis=0).mean();spec[k]=(pp[:,active].mean(axis=1)/ref).astype(float)
 rows=[];bp={}
 for lo,hi in bands:
  e=pp[(f>=lo)&(f<hi)].sum(0);bp[f'{lo}_{hi}']=e
  rows.append({'band_Hz':[lo,hi],'active_dB_relative_80_16k':Db(e[active].mean()/ref),'quiet_relative_active_dB':Db(e[quiet].mean()/e[active].mean()),'active_frame_p90_p10_dB':float(np.percentile(10*np.log10(e[active]+1e-30),90)-np.percentile(10*np.log10(e[active]+1e-30),10))})
 activepower=pp[(f>=80)&(f<16000)].sum(0)
 # within-source active strength bins, not source-adaptive masks
 by_strength=[]
 for lo,hi in [(-45,-35),(-35,-25),(-25,0)]:
  sel=(rdb>=lo)&(rdb<hi);den=activepower[sel].mean();by_strength.append({'dry_RMS_dBFS':[lo,hi],'frames':int(sel.sum()),'band_relative_dB':{key:Db(e[sel].mean()/den) for key,e in bp.items()}})
 allbp[k]=bp
 rr={'path':str(path),'frames':len(x),'duration_seconds':len(x)/sr,'finite':bool(np.isfinite(x).all()),'peak_dBFS':da(abs(x).max()),'digital_fullscale_samples':int((abs(x)>=1).sum()),'mono_energy_delta_dB':Db(np.mean(m*m)/np.mean(x*x)),'active_40ms_rms_percentiles_dBFS':{str(q):float(np.percentile(db[active40],q)) for q in [10,50,90,95,99]},'active_40ms_p90_p10_dB':float(np.percentile(db[active40],90)-np.percentile(db[active40],10)),'active_40ms_p95_p05_dB':float(np.percentile(db[active40],95)-np.percentile(db[active40],5)),'bands':rows,'by_dry_strength':by_strength}
 res['files'][k]=rr
for a,b in [('V10','V9'),('V10_core','dry'),('V10','original_wet')]:
 res['deltas'][a+'_minus_'+b]=[{'band_Hz':x['band_Hz'],'active_normalized_spectral_delta_dB':x['active_dB_relative_80_16k']-y['active_dB_relative_80_16k'],'quiet_to_active_delta_dB':x['quiet_relative_active_dB']-y['quiet_relative_active_dB']} for x,y in zip(res['files'][a]['bands'],res['files'][b]['bands'])]
# Actual summed low-mid density, rather than average of dB ratios.
res['lowmid_150_1200_dB_relative_80_16k']={}
for k in allbp:
 e=allbp[k]['150_300']+allbp[k]['300_600']+allbp[k]['600_1200'];p=np.sum(spec[k][(f>=150)&(f<1200)])
 res['lowmid_150_1200_dB_relative_80_16k'][k]=Db(p)
np.savez_compressed(O/'final_quality_spectra.npz',f=f,**spec)
(O/'final_quality.json').write_text(json.dumps(res,indent=2))
print(json.dumps({'dynamics':{k:x['active_40ms_p90_p10_dB'] for k,x in res['files'].items()},'lowmid':res['lowmid_150_1200_dB_relative_80_16k'],'deltas':res['deltas']},indent=2))
