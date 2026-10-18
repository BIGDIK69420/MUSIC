"""Read exported V13 audio back and verify its relation to the approved V12."""
from pathlib import Path
import json, re, subprocess
import numpy as np
from scipy import signal
from scipy.io import wavfile

P=Path('/workspace/audio-v13'); B=Path('/workspace/audio-v12')
SR=48000; N=10285140
v=json.loads((P/'validation.json').read_text()); ctl=np.load(P/'controls.npz')
def arr(p): return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def db(x): return float(20*np.log10(max(float(x),1e-15)))
def decode(p):
    r=subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','f32le','-ar',str(SR),'-ac','2','-'],check=True,capture_output=True)
    return np.frombuffer(r.stdout,dtype='float32').reshape(-1,2)
def loudness(x):
    r=subprocess.run(['ffmpeg','-hide_banner','-nostats','-f','f32le','-ar',str(SR),'-ac','2','-i','-',
      '-af','loudnorm=I=-16:TP=-1.3:LRA=8:print_format=json','-f','null','-'],input=x.astype('float32').tobytes(),capture_output=True,check=True)
    return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr.decode(),re.S).group())
def stats(x):
    m=x.mean(1); s=(x[:,0]-x[:,1])*.5
    return {'frames':len(x),'finite':bool(np.isfinite(x).all()),'peak_dBFS':db(np.max(abs(x))),
      'mono_fold_energy_dB':float(10*np.log10(np.mean(m*m)/np.mean(x*x))),
      'side_mid_dB':float(10*np.log10((np.mean(s*s)+1e-20)/np.mean(m*m)))}
out={'exports':{},'comparison':[],'source_checks':{},'tone':{}}
mapping={'MUSIC_v13_FINISH.wav':'master.f32','MUSIC_v13_VOCAL.wav':'vocal.f32',
 'MUSIC_v13_VOCAL_CORE.wav':'core_mix.f32','MUSIC_v13_VOCAL_FX.wav':'fx_mix.f32','MUSIC_v13_BEAT.wav':'beat.f32'}
for name,raw in mapping.items():
    sr,x=wavfile.read(P/name); assert x.dtype==np.int32
    x=x.astype('float32')/2147483648
    st=stats(x); st['quantization_max_error']=float(np.max(abs(x-arr(P/raw))))
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries',
      'stream=codec_name,sample_rate,channels,bits_per_sample','-of','json',str(P/name)],capture_output=True,text=True,check=True).stdout)['streams'][0]
    st['format']=probe
    assert sr==SR and len(x)==N and st['finite'] and np.max(abs(x))<1 and st['quantization_max_error']<3e-7
    assert probe['codec_name']=='pcm_s24le' and probe['bits_per_sample']==24 and probe['channels']==2
    out['exports'][name]=st
mp=decode(P/'MUSIC_v13_FINISH.mp3'); assert len(mp)==N and np.isfinite(mp).all() and np.max(abs(mp))<1
mpst=stats(mp)
mpst['approx_4x_peak_dBFS']=db(max(float(np.max(abs(signal.resample_poly(mp[i:i+20*SR],4,1,axis=0)))) for i in range(0,N,20*SR)))
assert mpst['approx_4x_peak_dBFS']<-.5
out['exports']['MUSIC_v13_FINISH.mp3']=mpst

core=arr(P/'core_mix.f32'); oldcore=arr(B/'core_mix.f32')
fx=arr(P/'fx_mix.f32'); vocal=arr(P/'vocal.f32')
beat=arr(P/'beat.f32'); oldbeat=arr(Path('/workspace/audio-clean/beat_clean.f32'))
checks=out['source_checks']
checks['core_plus_fx_max_error']=float(np.max(abs(core+fx-vocal)))
checks['vocal_plus_new_beat_max_error']=float(np.max(abs(vocal+beat-arr(P/'premaster.f32'))))
checks['double_preservation_max_error']=float(np.max(abs(arr(P/'doubles.f32')-arr(B/'doubles.f32'))))
checks['beat_side_preservation_max_error']=float(np.max(abs((beat[:,0]-beat[:,1])*.5-(oldbeat[:,0]-oldbeat[:,1])*.5)))
ride=np.interp(np.arange(N)/SR,ctl['times'],ctl['ride']).astype('float32')
expected=oldcore*(10**(ride[:,None]/20))*10**(v['vocal']['core_makeup_dB']/20)
checks['core_gain_only_max_error']=float(np.max(abs(core-expected)))
assert max(checks.values())<5e-7
out['core_LUFS']={name:float(loudness(x)['input_i']) for name,x in [('V12',oldcore),('V13',core)]}
assert abs(out['core_LUFS']['V13']-out['core_LUFS']['V12'])<.04

# Measure changes to the beat using common 10 ms masks and identical causal filters.
H=480; K=N//H; times=(np.arange(K)+.5)*.01
dry=np.interp(times,ctl['times'],ctl['drydb']); dose=np.interp(times,ctl['times'],ctl['beat_dose'])
active=(dry>-38)&(times>6)&(times<192)
weak=active&(dry<np.percentile(dry[active],100/3))
masks={'active':active,'weak':weak,'higher_dose':active&(dose>.5)}
out['beat_mid_energy_change_dB']={}
for lo,hi in [(40,150),(200,500),(900,1600),(2500,5000),(6000,12000)]:
    sos=signal.butter(2,[lo,hi],btype='bandpass',fs=SR,output='sos')
    powers=[]
    for x in [oldbeat,beat]:
        y=signal.sosfilt(sos,x.mean(1))[:K*H].reshape(K,H)
        powers.append(np.mean(y*y,axis=1))
    changes={label:float(10*np.log10(powers[1][mask].sum()/powers[0][mask].sum())) for label,mask in masks.items()}
    out['beat_mid_energy_change_dB'][f'{lo}-{hi}']=changes
assert abs(out['beat_mid_energy_change_dB']['40-150']['active'])<.05
assert -1.6<out['beat_mid_energy_change_dB']['900-1600']['higher_dose']<-.1

# Shared-mask, normalized spectra and envelope ranges track unintended broad changes.
bands=[(80,150),(150,300),(300,600),(600,1200),(1200,2500),(2500,5000),(5000,10000),(10000,16000)]
def tone(p):
    x=arr(p); m=x.mean(1)
    f,t,z=signal.stft(m,fs=SR,nperseg=4096,noverlap=2048,boundary=None)
    mask=np.interp(t,ctl['times'],ctl['drydb'])>-38
    e=np.mean(abs(z[:,mask])**2,axis=1); den=e[(f>=300)&(f<5000)].sum()
    result={'spectrum':{f'{lo}-{hi}':float(10*np.log10(e[(f>=lo)&(f<hi)].sum()/den)) for lo,hi in bands}}
    h=1920; k=len(m)//h
    lev=10*np.log10(np.mean(m[:k*h].reshape(k,h)**2,axis=1)+1e-20)
    mask=np.interp((np.arange(k)+.5)*.04,ctl['times'],ctl['drydb'])>-38
    result['active_p90_p10_dB']=float(np.percentile(lev[mask],90)-np.percentile(lev[mask],10))
    return result
for name,p in [('V12_core',B/'core_mix.f32'),('V13_core',P/'core_mix.f32'),('V12_vocal',B/'vocal.f32'),('V13_vocal',P/'vocal.f32')]:
    out['tone'][name]=tone(p)
out['tone_delta']={kind:{band:out['tone']['V13_'+kind]['spectrum'][band]-out['tone']['V12_'+kind]['spectrum'][band]
 for band in out['tone']['V12_'+kind]['spectrum']} for kind in ['core','vocal']}
assert max(abs(a) for d in out['tone_delta'].values() for a in d.values())<.4
assert out['tone']['V13_core']['active_p90_p10_dB']>out['tone']['V12_core']['active_p90_p10_dB']-.4
alignment=[]
for start in [12,60,100,114,163,179]:
    a=signal.resample_poly(np.array(oldcore[start*SR:(start+2)*SR].mean(1)),1,4)
    b=signal.resample_poly(np.array(core[start*SR:(start+2)*SR].mean(1)),1,4)
    corr=signal.correlate(b,a,method='fft'); center=len(a)-1; span=24
    lag=int(np.argmax(corr[center-span:center+span+1])-span)
    alignment.append({'start_s':start,'lag_ms':lag/12})
assert max(abs(x['lag_ms']) for x in alignment)==0
out['alignment']=alignment

comp=decode(P/'MUSIC_v13_COMPARE.mp3')
assert len(comp)==70*SR and np.max(abs(comp))<1 and np.isfinite(comp).all()
for row in v['comparison']:
    z=comp[round(row['start_s']*SR):round(row['end_s']*SR)]; m=loudness(z)
    assert abs(float(m['input_i'])-row['target_LUFS'])<.12
    out['comparison'].append({'label':row['label'],'decoded_LUFS':float(m['input_i']),'decoded_dBTP':float(m['input_tp'])})
out['status']='PASS'
out['limits']='Signal validation, not subjective listening or proof of aesthetic improvement. Band energies do not establish perceptual masking. Oversampling peak and shared-mask spectra have finite resolution.'
(P/'quality-check.json').write_text(json.dumps(out,indent=2))
print(json.dumps({key:out[key] for key in ['status','source_checks','core_LUFS','beat_mid_energy_change_dB','tone_delta','alignment','comparison']},indent=2))
