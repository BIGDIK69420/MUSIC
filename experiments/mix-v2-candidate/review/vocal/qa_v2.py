from pathlib import Path
import json, hashlib
import numpy as np
from scipy import signal

O=Path('/workspace/audio-v2-review-vocal');B=Path('/workspace/audio-v13');C=Path('/workspace/audio-v2-candidate');SR=48000;H=1920
def read(p):return np.memmap(p,mode='r',dtype=np.float32).reshape(-1,2)
def db(p):return 10*np.log10(np.maximum(p,1e-30))
def env(x):
 n=len(x)//H*H
 return np.mean(x[:n].reshape(-1,H)**2,axis=1)
def ms(x):return x.mean(1),(x[:,0]-x[:,1])/2
old=read(B/'core_mix.f32');new=read(C/'core_mix.f32');n=len(old);t=np.arange(n//H)*.04+.02
ctrl=np.load(B/'controls.npz');candidate=np.load(C/'controls.npz')
active=np.interp(t,ctrl['times'],ctrl['activity'])>.8
voiced=np.interp(t,ctrl['times'],ctrl['voiced'])>.7
dry=np.interp(t,ctrl['times'],ctrl['drydb']);entry=np.interp(t,ctrl['times'],ctrl['entry'])>.4
weak=active&voiced&(dry<np.percentile(dry[active&voiced],40));strong=active&voiced&(dry>np.percentile(dry[active&voiced],65))
masks={'active':active,'voiced':active&voiced,'weak_voiced':weak,'strong_voiced':strong,'entry':entry,'gap':~active}
out={'files':{},'states':{},'alignment':[],'controls':{},'limitations':'Same V1 masks and 40 ms windows as initial review. Spectral/routing checks are not subjective listening.'}
for name in ['core_mix','vocal','doubles','echo','shallow','deep','fx_mix']:
 x=read(B/(name+'.f32'));y=read(C/(name+'.f32'))
 out['files'][name]={'shape_match':x.shape==y.shape,'finite':bool(np.isfinite(y).all()),'peak':float(abs(y).max()),'byte_exact':bool(np.array_equal(x,y))}
 if name in ['core_mix','vocal','doubles','fx_mix']:
  xm,xs=ms(x);ym,ys=ms(y);px=env(xm);py=env(ym);sx=env(xs);sy=env(ys)
  for state,mask in masks.items():
   z=out['states'].setdefault(state,{})
   z[name+'_mid_energy_change_dB']=float(db(py[mask].sum()/px[mask].sum()))
   z[name+'_SM_before_dB']=float(db(sx[mask].sum()/px[mask].sum()))
   z[name+'_SM_after_dB']=float(db(sy[mask].sum()/py[mask].sum()))
   z[name+'_SM_change_dB']=z[name+'_SM_after_dB']-z[name+'_SM_before_dB']
  out['files'][name]['max_mid_sample_difference']=float(abs(ym-xm).max())
  out['files'][name]['mono_fold_energy_change_dB']=float(db(np.mean(ym*ym)/np.mean(xm*xm)))
  if name=='core_mix':
   for a,b in [(40,70),(100,130)]:
    p=px[int(a/.04):int(b/.04)];q=py[int(a/.04):int(b/.04)];sel=db(p)>np.percentile(db(p),95)-20
    out.setdefault('core_dynamics',{})[f'{a}_{b}']={'p90_p10_before':float(np.percentile(db(p[sel]),90)-np.percentile(db(p[sel]),10)),'p90_p10_after':float(np.percentile(db(q[sel]),90)-np.percentile(db(q[sel]),10)),'p95_p50_before':float(np.percentile(db(p[sel]),95)-np.percentile(db(p[sel]),50)),'p95_p50_after':float(np.percentile(db(q[sel]),95)-np.percentile(db(q[sel]),50))}
   for lo,hi in [(150,400),(400,1200),(1200,5000),(5000,10000),(10000,16000)]:
    filt=signal.butter(2,[lo,hi],fs=SR,btype='bandpass',output='sos')
    bp=env(signal.sosfilt(filt,xm));bq=env(signal.sosfilt(filt,ym))
    for state,mask in masks.items():out['states'][state][f'core_band_{lo}_{hi}_change_dB']=float(db(bq[mask].sum()/bp[mask].sum()))
   for start in [7,38,61,106,143,175]:
    a=xm[int(start*SR):int((start+3)*SR)].astype(np.float64);b=ym[int(start*SR):int((start+3)*SR)].astype(np.float64)
    cor=signal.correlate(b,a,mode='full',method='fft');mid=len(a)-1;lag=int(np.argmax(cor[mid-96:mid+97])-96)
    out['alignment'].append({'start_seconds':start,'best_lag_samples':lag,'zero_lag_correlation':float(np.corrcoef(a,b)[0,1])})
cc=np.interp(t,candidate['times'],candidate['edge']);lift=np.interp(t,candidate['times'],candidate['side_lift_dB'])
for state,mask in masks.items():
 out['controls'][state]={'edge_p50_p90_p95_p99':np.percentile(cc[mask],[50,90,95,99]).tolist(),'edge_over_025_seconds':float(np.sum(mask&(cc>.25))*.04),'side_lift_p50_p90_p95_p99':np.percentile(lift[mask],[50,90,95,99]).tolist(),'side_lift_above_025_seconds':float(np.sum(mask&(lift>.25))*.04)}
# Route consistency in original float32 summing order; independently report all errors.
core=read(C/'core_mix.f32');fx=read(C/'fx_mix.f32');v=read(C/'vocal.f32')
d=read(C/'doubles.f32');e=read(C/'echo.f32');s=read(C/'shallow.f32');deep=read(C/'deep.f32')
out['routing']={'core_plus_fx_vocal_max_abs_error':float(abs((core+fx)-v).max()),'layer_sum_fx_max_abs_error':float(abs(((d+e)+s)+deep-fx).max())}
checks={'all_finite_and_shapes':all(x['finite'] and x['shape_match'] for x in out['files'].values()),'three_returns_exact':all(out['files'][k]['byte_exact'] for k in ['echo','shallow','deep']),'doubles_mid_roundoff_only':out['files']['doubles']['max_mid_sample_difference']<2e-8,'fx_mid_roundoff_only':out['files']['fx_mix']['max_mid_sample_difference']<3e-8,'all_lead_lags_zero':all(x['best_lag_samples']==0 for x in out['alignment']),'active_HF_change_small':-.4<out['states']['active']['core_band_5000_10000_change_dB']<.1,'strong_vowel_HF_preserved':abs(out['states']['strong_voiced']['core_band_5000_10000_change_dB'])<.1,'strong_width_preserved':abs(out['states']['strong_voiced']['vocal_SM_change_dB'])<.15,'mono_change_small':abs(out['files']['vocal']['mono_fold_energy_change_dB'])<.1}
out['checks']=checks;out['pass']=all(checks.values())
(O/'qa_v2.json').write_text(json.dumps(out,indent=2));print(json.dumps({'checks':checks,'states':out['states'],'core_dynamics':out['core_dynamics'],'alignment':out['alignment']},indent=2))
