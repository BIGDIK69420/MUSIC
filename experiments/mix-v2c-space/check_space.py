"""Verify balance, routing, spectral change and stereo behavior independently."""
from pathlib import Path
import hashlib,json
import numpy as np
from scipy import signal

P=Path('/workspace/audio-v2c-space');V=Path('/workspace/audio-v2-candidate');B=Path('/workspace/audio-v2b-balance')
SR=48000;N=10285140;H=480;K=N//H
def arr(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def power(x):return float(np.mean(np.asarray(x,dtype='float64')**2))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
design=json.loads((P/'space-design.json').read_text())
for path,digest in design['unchanged_sources'].items():assert sha(Path(path))==digest

old=arr(V/'vocal.f32');new=arr(P/'vocal.f32');rv=arr(P/'reverb.f32')
expected=arr(V/'core_mix.f32')+arr(V/'doubles.f32')+arr(V/'echo.f32')+rv
routing_error=float(np.max(abs(new-expected)));assert routing_error<1e-7
prem_error=float(np.max(abs(arr(P/'premaster.f32')-(arr(B/'beat.f32')+new))));assert prem_error==0
dry_balance_error=float(np.max(abs((arr(P/'premaster.f32')-arr(P/'fx_mix.f32'))-(arr(V/'core_mix.f32')+arr(B/'beat.f32')))))
assert dry_balance_error<1e-7

c=np.load(V/'controls.npz');t=(np.arange(K)+.5)*.01
active=np.interp(t,c['times'],c['drydb'])>-38
def spectral(x,lo,hi):
    z=signal.sosfilt(signal.butter(3,[lo,hi],fs=SR,btype='bandpass',output='sos'),x,axis=0)
    e=np.mean(z[:K*H].reshape(K,H,2)**2,axis=(1,2));return float(np.mean(e[active]))
bands={}
for lo,hi in [(80,250),(250,700),(700,1600),(1600,4000),(4000,9000)]:
    a=spectral(old,lo,hi);b=spectral(new,lo,hi);r=spectral(rv,lo,hi)
    delta=float(10*np.log10(b/a));assert abs(delta)<.2
    bands[f'{lo}-{hi}_Hz']={'active_vocal_change_dB':delta,'new_reverb_RMS_dBFS':float(10*np.log10(r))}
stereo={}
for name,x in [('V2B_vocal',old),('V2C_vocal',new),('V2C_reverb',rv),('V2B_premaster',arr(B/'premaster.f32')),('V2C_premaster',arr(P/'premaster.f32'))]:
    fold=float(10*np.log10(power(x.mean(1))/power(x)))
    stereo[name]={'mono_fold_energy_change_dB':fold,'LR_correlation':float(np.corrcoef(x[::4].T)[0,1])}
assert stereo['V2C_vocal']['mono_fold_energy_change_dB']>-.7
assert stereo['V2C_premaster']['mono_fold_energy_change_dB']>-.7
assert stereo['V2C_reverb']['LR_correlation']>0

ir={}
for name in ['shallow','deep']:
    h=arr(P/(name+'_ir.f32'));e=np.mean(h.astype('float64')**2,axis=1)
    edc=np.cumsum(e[::-1])[::-1];edc=10*np.log10(np.maximum(edc/edc[0],1e-20))
    crossings={str(th):float(np.flatnonzero(edc<th)[0]/SR) for th in [-10,-30,-60]}
    ir[name]={'first_nonzero_ms':float(np.flatnonzero(e>1e-20)[0]*1000/SR),'energy_decay_crossing_s':crossings,
              'LR_correlation':float(np.corrcoef(h.T)[0,1])}
    assert ir[name]['first_nonzero_ms']>=1000*design[name]['ir']['predelay']

# Count return energy in unvoiced gaps only as a diagnostic, not evidence of noise.
end=rv[-2*SR:];assert np.max(abs(end))<1e-8
out={'status':'PASS','source_hashes_unchanged':True,
 'routing_max_float_error':routing_error,'premaster_sum_error':prem_error,'lead_plus_beat_balance_residual':dry_balance_error,
 'active_vocal_band_changes':bands,'stereo':stereo,'impulse_responses':ir,
 'last_two_seconds_reverb_peak':float(np.max(abs(end))),
 'limits':'Only exported external return energy is isolated. CORE includes printed effects. Mono/spectral checks cannot establish the perceived room size, naturalness, masking or artistic fit.'}
(P/'space-check.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
