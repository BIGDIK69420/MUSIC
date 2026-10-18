"""Read exported V12 files back; compare tone/dynamics to approved V11."""
from pathlib import Path
import json,re,subprocess
import numpy as np
from scipy import signal,ndimage
from scipy.io import wavfile

P=Path('/workspace/audio-v12');B=Path('/workspace/audio-v11');SR=48000;N=10285140
v=json.loads((P/'validation.json').read_text());old=json.loads((B/'validation.json').read_text())
ctl=np.load(P/'controls.npz')
def arr(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def db(x):return float(20*np.log10(max(float(x),1e-15)))
def decode(p):
    r=subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','f32le','-ar',str(SR),'-ac','2','-'],check=True,capture_output=True)
    return np.frombuffer(r.stdout,dtype='float32').reshape(-1,2)
def loudness(x):
    r=subprocess.run(['ffmpeg','-hide_banner','-nostats','-f','f32le','-ar',str(SR),'-ac','2','-i','-',
      '-af','loudnorm=I=-16:TP=-1.3:LRA=8:print_format=json','-f','null','-'],input=x.astype('float32').tobytes(),capture_output=True,check=True)
    return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr.decode(),re.S).group())
def signal_stats(x):
    m=x.mean(1);s=(x[:,0]-x[:,1])*.5
    return {'frames':len(x),'finite':bool(np.isfinite(x).all()),'peak_dBFS':db(np.max(abs(x))),
      'mono_fold_energy_dB':float(10*np.log10(np.mean(m*m)/np.mean(x*x))),
      'side_mid_dB':float(10*np.log10((np.mean(s*s)+1e-20)/np.mean(m*m)))}
out={'exports':{},'comparison':[],'source_checks':{},'tone':{}}
mapping={'MUSIC_v12_POLISH.wav':'master.f32','MUSIC_v12_VOCAL.wav':'vocal.f32',
         'MUSIC_v12_VOCAL_CORE.wav':'core_mix.f32','MUSIC_v12_VOCAL_FX.wav':'fx_mix.f32'}
for name,raw in mapping.items():
    sr,x=wavfile.read(P/name);assert x.dtype==np.int32;x=x.astype('float32')/2147483648
    st=signal_stats(x);st['quantization_max_error']=float(np.max(abs(x-arr(P/raw))))
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries',
      'stream=codec_name,sample_rate,channels,bits_per_sample','-of','json',str(P/name)],capture_output=True,text=True,check=True).stdout)['streams'][0]
    st['format']=probe
    assert sr==SR and len(x)==N and st['finite'] and np.max(abs(x))<1 and st['quantization_max_error']<3e-7
    assert probe['codec_name']=='pcm_s24le' and probe['bits_per_sample']==24 and probe['channels']==2
    out['exports'][name]=st
mp=decode(P/'MUSIC_v12_POLISH.mp3');assert len(mp)==N and np.isfinite(mp).all() and np.max(abs(mp))<1
st=signal_stats(mp);st['approx_4x_peak_dBFS']=db(max(float(np.max(abs(signal.resample_poly(mp[i:i+20*SR],4,1,axis=0)))) for i in range(0,N,20*SR)))
assert st['approx_4x_peak_dBFS']<-.5;out['exports']['MUSIC_v12_POLISH.mp3']=st
core=arr(P/'core_mix.f32');fx=arr(P/'fx_mix.f32');vocal=arr(P/'vocal.f32')
out['source_checks']['core_plus_fx_max_error']=float(np.max(abs(core+fx-vocal)))
out['source_checks']['beat_preservation_max_error']=float(np.max(abs(vocal+arr(Path('/workspace/audio-clean/beat_clean.f32'))-arr(P/'premaster.f32'))))
factor=10**(old['levels']['vocal_post_FX_gain_dB']/20)*old['levels']['FX_cap']
out['source_checks']['double_mid_preservation_max_error']=float(np.max(abs(arr(P/'doubles.f32').mean(1)-(arr(B/'doubles.f32')*factor).mean(1))))
out['source_checks']['shallow_preservation_max_error']=float(np.max(abs(arr(P/'shallow.f32')-arr(B/'shallow.f32')*factor)))
assert max(out['source_checks'].values())<5e-7

# Compare shared-mask Mid spectra, rather than interpreting a louder signal as tonal improvement.
bands=[(80,150),(150,300),(300,600),(600,1200),(1200,2500),(2500,5000),(5000,10000),(10000,16000)]
def tone(p):
    x=arr(p);m=x.mean(1);f,t,z=signal.stft(m,fs=SR,nperseg=4096,noverlap=2048,boundary=None)
    mask=np.interp(t,ctl['times'],ctl['drydb'])>-38
    e=np.mean(abs(z[:,mask])**2,axis=1);den=e[(f>=300)&(f<5000)].sum()
    result={'spectrum':{f'{lo}-{hi}':float(10*np.log10(e[(f>=lo)&(f<hi)].sum()/den)) for lo,hi in bands}}
    h=1920;k=len(m)//h;lev=10*np.log10(np.mean(m[:k*h].reshape(k,h)**2,axis=1)+1e-20)
    active=np.interp((np.arange(k)+.5)*.04,ctl['times'],ctl['drydb'])>-38
    result['active_p90_p10_dB']=float(np.percentile(lev[active],90)-np.percentile(lev[active],10))
    result['active_p95_p50_dB']=float(np.percentile(lev[active],95)-np.percentile(lev[active],50))
    return result
for name,p in [('V11_core',B/'core_mix.f32'),('V12_core',P/'core_mix.f32'),('V11_vocal',B/'vocal.f32'),('V12_vocal',P/'vocal.f32')]:out['tone'][name]=tone(p)
out['tone_delta']={kind:{band:out['tone']['V12_'+kind]['spectrum'][band]-out['tone']['V11_'+kind]['spectrum'][band] for band in out['tone']['V11_'+kind]['spectrum']} for kind in ['core','vocal']}
assert max(abs(a) for d in out['tone_delta'].values() for a in d.values())<1.3
assert out['tone']['V12_core']['active_p90_p10_dB']>out['tone']['V11_core']['active_p90_p10_dB']-.8

# Check lead alignment on several phrases; EQ can change fine phase without changing timing.
alignment=[]
for start in [12,60,100,114,163,179]:
    a=np.array(arr(B/'core_mix.f32')[start*SR:(start+2)*SR].mean(1))
    b=np.array(core[start*SR:(start+2)*SR].mean(1))
    a=signal.resample_poly(a,1,4);b=signal.resample_poly(b,1,4)
    corr=signal.correlate(b,a,method='fft');center=len(a)-1;span=24
    lag=int(np.argmax(corr[center-span:center+span+1])-span)
    alignment.append({'start_s':start,'lag_ms':lag/12})
assert max(abs(x['lag_ms']) for x in alignment)<.5
out['alignment']=alignment

comp=decode(P/'MUSIC_v12_COMPARE.mp3');assert len(comp)==round(53.5*SR) and np.max(abs(comp))<1 and np.isfinite(comp).all()
for row in v['comparison']:
    z=comp[round(row['start_s']*SR):round(row['end_s']*SR)];m=loudness(z)
    assert abs(float(m['input_i'])-row['target_LUFS'])<.12
    out['comparison'].append({'label':row['label'],'decoded_LUFS':float(m['input_i']),'decoded_dBTP':float(m['input_tp'])})
out['status']='PASS';out['limits']='Signal validation, not subjective listening or proof of aesthetic perfection. Approximate oversampling peak and shared-mask spectrum checks have finite resolution.'
(P/'quality-check.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'status':out['status'],'source_checks':out['source_checks'],'tone_delta':out['tone_delta'],
 'dynamics':{k:a['active_p90_p10_dB'] for k,a in out['tone'].items()},'alignment':alignment,'comparison':out['comparison'],'MP3_4x_peak_dBFS':st['approx_4x_peak_dBFS']},indent=2))
