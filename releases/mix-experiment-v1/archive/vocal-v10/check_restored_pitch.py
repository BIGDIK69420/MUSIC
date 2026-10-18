from pathlib import Path
import numpy as np,json
from scipy import signal
P=Path('/workspace/audio-v10-pitch');O=Path('/workspace/audio-v10-review');R=Path('/workspace/audio-rebuild');sr=48000
x=np.fromfile(P/'dry_tuned_mono.f32',dtype='float32');z=np.fromfile(P/'restored_tuned_mono.f32',dtype='float32')
assert len(x)==len(z) and np.isfinite(z).all()
r={'method':'Existing trustworthy period frames, sampled every fourth valid frame; normalized autocorrelation with parabolic refinement within ±15% of original dry F0. This checks tuning preservation without rerunning a whole-track neural estimator.','duration_seconds':len(z)/sr,'sample_count':len(z),'source_finite':bool(np.isfinite(z).all()),'alignment':[]}
for sec in [6,16,31,57,63,102,109,123,141,159,173,181]:
 a=signal.resample_poly(x[int(sec*sr):int((sec+2)*sr)],1,4);b=signal.resample_poly(z[int(sec*sr):int((sec+2)*sr)],1,4)
 a=a-a.mean();b=b-b.mean();cc=signal.correlate(b,a,mode='full',method='fft');lags=signal.correlation_lags(len(b),len(a),mode='full');sel=abs(lags)<=300;k=np.argmax(cc[sel]);lag=int(lags[sel][k]);corr=float(cc[sel][k]/np.sqrt(np.dot(a,a)*np.dot(b,b)))
 r['alignment'].append({'start_s':sec,'best_lag_samples_at_12k':lag,'best_lag_ms':lag/12,'normalized_correlation':corr})
c=np.load(P/'comparison.npz');prior=np.load(P/'periods.npz');t=c['t'];ids=np.flatnonzero(prior['valid'])[::4];expected=c['dry'];allfreq={'old_tuned':prior['tuned'][ids],'wet_reference':prior['mixed'][ids]};allqual={'old_tuned':prior['tuned_q'][ids],'wet_reference':prior['mixed_q'][ids]}
inputs={'restored_tuned':z}
if (R/'core.f32').exists() and (R/'core.f32').stat().st_size==len(z)*8:
 inputs['final_core']=np.memmap(R/'core.f32',dtype='float32').reshape(-1,2).mean(1)
elif (R/'core_peak_safe.f32').exists() and (R/'core_peak_safe.f32').stat().st_size==len(z)*8:
 inputs['core_peak_safe']=np.memmap(R/'core_peak_safe.f32',dtype='float32').reshape(-1,2).mean(1)
for name,v in inputs.items():
 v=signal.resample_poly(v.astype('float64'),1,3);f=np.zeros(len(ids));q=np.zeros(len(ids))
 for j,i in enumerate(ids):
  k=int(t[i]*16000);y=v[max(0,k-640):min(len(v),k+640)];y=y-y.mean();lo=max(1,int(16000/expected[i]/1.15));hi=min(len(y)//2,int(16000/expected[i]*1.15));lags=np.arange(lo,hi+1)
  a=np.array([2*np.dot(y[:-lag],y[lag:])/(np.dot(y[:-lag],y[:-lag])+np.dot(y[lag:],y[lag:])+1e-20) for lag in lags]);k=int(np.argmax(a));lag=float(lags[k]);q[j]=a[k]
  if 0<k<len(a)-1:
   den=a[k-1]-2*a[k]+a[k+1]
   if abs(den)>1e-10:lag+=(a[k-1]-a[k+1])/(2*den)
  f[j]=16000/lag
 allfreq[name]=f;allqual[name]=q
r['pitch']={}
for name in inputs:
 keep=(allqual[name]>.7)&(allqual['old_tuned']>.7)&(allqual['wet_reference']>.7)
 for ref in ['old_tuned','wet_reference']:
  delta=1200*np.log2(allfreq[name][keep]/allfreq[ref][keep]);r['pitch'][name+'_vs_'+ref]={'paired_frames':int(keep.sum()),'absolute_cents_percentiles':dict(zip(['50','90','95','99'],np.percentile(abs(delta),[50,90,95,99]).tolist())),'cents_RMS':float(np.sqrt(np.mean(delta**2))),'percent_above_50c':float(100*np.mean(abs(delta)>50))}
 r['pitch'][name+'_periodicity_pass_percent']=float(100*np.mean(allqual[name]>.7))
# Frame dynamic comparison over one shared activity mask.
dryr=np.load('/workspace/audio-analysis/dry_rms.npy');h=1920;k=len(z)//h;act=dryr[:k]>10**(-38/20)
r['active_40ms_dynamics']={}
for name,v in {'old_tuned':x,**inputs}.items():
 en=np.mean(v[:k*h].reshape(k,h).astype('float64')**2,axis=1);db=10*np.log10(np.maximum(en,1e-20));a=db[act]
 r['active_40ms_dynamics'][name]={'p90_minus_p10_dB':float(np.percentile(a,90)-np.percentile(a,10)),'p95_minus_p50_dB':float(np.percentile(a,95)-np.percentile(a,50)),'median_dBFS':float(np.median(a))}
(O/'restored_pitch_alignment.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
