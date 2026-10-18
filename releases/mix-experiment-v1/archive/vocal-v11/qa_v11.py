"""Read-only independent output validation. Writes only into the review folder."""
from pathlib import Path
import json, subprocess
import numpy as np
from scipy import signal
from scipy.io import wavfile

P=Path('/workspace/audio-v11');R=Path('/workspace/audio-v11-review');SR=48000
source=Path('/workspace/audio-reference/vocal_final.f32');N=source.stat().st_size//8
validation=json.loads((P/'validation.json').read_text())
def raw(name,mono=False):
    q=np.memmap(P/(name+'.f32'),dtype='float32',mode='r')
    return q if mono else q.reshape(-1,2)
def db(z):return float(20*np.log10(max(float(z),1e-15)))
def rawstat(x):
    return {'frames':len(x),'finite':bool(np.isfinite(x).all()),'peak_dBFS':db(np.max(abs(x))),'samples_abs_ge_one':int(np.sum(abs(x)>=1)),'last_20ms_peak_dBFS':db(np.max(abs(x[-960:])))}
def difference(a,b):return {'max_abs_sample_error':float(np.max(abs(a-b))),'error_RMS_dBFS':db(np.sqrt(np.mean((a.astype('float64')-b)**2)))}
result={'source_frames':N,'expected_duration_s':N/SR,'raw':{},'sum_identity':{},'exports':{}}
for name in ['core','doubles','echo','shallow','deep','core_mix','fx_mix','vocal','premaster','master']:
    x=raw(name);result['raw'][name]=rawstat(x);assert len(x)==N and np.isfinite(x).all(),name
result['raw']['harmonic_color_mono']=rawstat(raw('harmonic_color_mono',True))
core=raw('core_mix');fx=raw('fx_mix');vocal=raw('vocal');pre=raw('premaster');master=raw('master')
result['sum_identity']['core_plus_fx_equals_vocal']=difference(core+fx,vocal)
beat=np.memmap('/workspace/audio-clean/beat_clean.f32',dtype='float32',mode='r').reshape(-1,2)
result['sum_identity']['vocal_plus_beat_equals_premaster']=difference(beat+vocal,pre)
for d in result['sum_identity'].values():assert d['max_abs_sample_error']<5e-7
ctl=np.load(P/'controls.npz');times=ctl['times'];voiced=ctl['voiced']
gate=np.interp(np.arange(N)/SR,times,voiced).astype('float32')
color=raw('harmonic_color_mono',True);outside=gate<1e-4
result['harmonic_outside_gate_peak_dBFS']=db(np.max(abs(color[outside])))
result['backing_mono_frames']=[int((P/f'backing_{i}.f32').stat().st_size//4) for i in range(2)]
assert all(abs(n-N)<SR*.03 for n in result['backing_mono_frames'])
for name,src in [('MUSIC_v11_1CALL.wav','master'),('MUSIC_v11_VOCAL.wav','vocal'),('MUSIC_v11_VOCAL_CORE.wav','core_mix'),('MUSIC_v11_VOCAL_FX.wav','fx_mix')]:
    fs,x=wavfile.read(P/name);x=x.astype('float32')/2147483648.
    row=rawstat(x);row['sample_rate']=fs;row['channels']=x.shape[1];row['quantization_error_vs_float']=difference(x,raw(src));result['exports'][name]=row
    assert fs==SR and len(x)==N and x.shape[1]==2 and np.isfinite(x).all() and np.max(abs(x))<1,name
    assert row['quantization_error_vs_float']['max_abs_sample_error']<3e-7,name
mp3=P/'MUSIC_v11_1CALL.mp3'
pr=subprocess.run(['ffmpeg','-v','error','-i',str(mp3),'-f','f32le','-acodec','pcm_f32le','-'],check=True,capture_output=True)
x=np.frombuffer(pr.stdout,dtype='float32').reshape(-1,2);result['exports'][mp3.name]=rawstat(x)
assert len(x)==N and np.isfinite(x).all() and np.max(abs(x))<1
# Independent approximate 4x peaks, different implementation from ffmpeg loudnorm.
for name,x in [('master',master),('mp3_decoded',x)]:
    pk=max(float(np.max(abs(signal.resample_poly(x[i:i+20*SR],4,1,axis=0)))) for i in range(0,N,20*SR))
    mono=x.mean(axis=1);e=float(np.mean(x*x));em=float(np.mean(mono*mono));side=(x[:,0]-x[:,1])*.5
    result[name+'_compatibility']={'approx_4x_peak_dBFS':db(pk),'LR_correlation':float(np.corrcoef(x[::10].T)[0,1]),'mono_fold_energy_change_dB':float(10*np.log10(em/e)),'side_mid_energy_dB':float(10*np.log10(np.mean(side*side)/em))}
last=validation['master']['passes'][-1]
result['metadata_checks']={'last_master_pass':last,'reported_master':{k:validation['master'][k] for k in ['WAV_LUFS','WAV_dBTP','MP3_LUFS','MP3_dBTP']},'passes':len(validation['master']['passes'])}
assert last['LUFS']==validation['master']['WAV_LUFS'] and last['dBTP']==validation['master']['WAV_dBTP']
assert len(validation['master']['passes'])<5 or abs(last['LUFS']+11.5)<.05
(R/'qa_v11.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
