from pathlib import Path
import json
import numpy as np
from scipy import signal,ndimage
P=Path('/workspace/audio-v11');O=Path('/workspace/audio-v11-review');SR=48000;H=480
raw=lambda name:np.memmap(P/(name+'.f32'),dtype='float32',mode='r').reshape(-1,2)
ctl=np.load(P/'controls.npz');t=ctl['times'];v=ctl['voiced'];drydb=ctl['drydb'];N=len(raw('core_mix'))
# The control is smoothed; define support at -60 dB amplitude then exclude 100 ms either side.
selected=v>.001
far=~ndimage.maximum_filter1d(selected.astype(int),size=21,mode='constant').astype(bool)
far_samples=np.interp(np.arange(N)/SR,t,far.astype(float))>.999
vowel_samples=np.interp(np.arange(N)/SR,t,v)>.65
active=np.interp(np.arange(N)/SR,t,(drydb>-38).astype(float))>.9
D=raw('doubles');core=raw('core_mix');full=raw('vocal');fx=raw('fx_mix')
rms=lambda x:float(np.sqrt(np.mean(np.asarray(x,dtype='float64')**2)))
db=lambda x:float(20*np.log10(max(float(x),1e-15)))
res={'double_far_outside_gate':{'definition':'control voiced amplitude <= 0.001, >100 ms from any frame above that threshold','outside_seconds':float(far_samples.sum()/SR),'selected_vowel_RMS_dBFS':db(rms(D[vowel_samples])),'far_outside_RMS_dBFS':db(rms(D[far_samples])),'outside_to_selected_RMS_dB':db(rms(D[far_samples])/rms(D[vowel_samples])),'outside_peak_dBFS':db(abs(D[far_samples]).max())},'bands':{}}
for band in [(250,1200),(250,600),(600,1200)]:
    sos=signal.butter(3,band,fs=SR,btype='bandpass',output='sos')
    c=signal.sosfilt(sos,core.mean(axis=1));f=signal.sosfilt(sos,full.mean(axis=1));e=signal.sosfilt(sos,fx.mean(axis=1))
    rec={}
    for name,mask in [('active',active),('sustained_vowels',vowel_samples),('active_far_outside',active&far_samples)]:
        ec=np.mean(c[mask]**2);ef=np.mean(f[mask]**2)
        rec[name]={'full_vs_core_energy_dB':float(10*np.log10(ef/ec)),'cross_term_vs_core_energy_ratio':float(2*np.mean(c[mask]*e[mask])/ec)}
    W=1920;n=len(c)//W;c2=np.mean(c[:n*W].reshape(n,W)**2,axis=1);f2=np.mean(f[:n*W].reshape(n,W)**2,axis=1)
    a=np.mean(active[:n*W].reshape(n,W),axis=1)>.75
    a &= c2>1e-7
    rr=10*np.log10(f2[a]/c2[a]);rec['active_40ms_ratio_dB_percentiles']={str(p):float(np.percentile(rr,p)) for p in [0,1,5,50,95,99,100]};rec['percent_active_frames_below_minus1dB']=float(np.mean(rr< -1)*100);rec['percent_active_frames_below_minus3dB']=float(np.mean(rr< -3)*100)
    res['bands'][f'{band[0]}-{band[1]}']=rec
(O/'qa_vowel_and_sum.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
