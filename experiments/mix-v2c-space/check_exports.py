from pathlib import Path
import json,re,subprocess
import numpy as np
from scipy.io import wavfile
P=Path('/workspace/audio-v2c-space');SR=48000;N=10285140
def raw(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def decode(p):
    r=subprocess.run(['ffmpeg','-v','error','-i',str(p),'-ar',str(SR),'-ac','2','-f','f32le','-'],capture_output=True,check=True)
    return np.frombuffer(r.stdout,dtype='float32').reshape(-1,2)
def measure(x):
    r=subprocess.run(['ffmpeg','-hide_banner','-nostats','-f','f32le','-ar',str(SR),'-ac','2','-i','-',
      '-af','loudnorm=I=-16:TP=-1.3:LRA=8:print_format=json','-f','null','-'],input=x.tobytes(),capture_output=True,check=True)
    return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr.decode(),re.S).group())
result={'exports':{},'comparisons':{}}
for suffix,source in [('', 'master.f32'),('_VOCAL','vocal.f32'),('_VOCAL_FX','fx_mix.f32'),('_REVERB','reverb.f32')]:
    name='MUSIC_MIX_V2C_SPACE'+suffix+'.wav';sr,x=wavfile.read(P/name)
    assert x.dtype==np.int32;x=x.astype('float32')/2147483648
    error=float(np.max(abs(x-raw(P/source))))
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries',
      'stream=codec_name,sample_rate,channels,bits_per_sample','-of','json',str(P/name)],capture_output=True,text=True,check=True).stdout)['streams'][0]
    assert len(x)==N and sr==SR and np.isfinite(x).all() and np.max(abs(x))<1 and error<3e-7
    assert probe['codec_name']=='pcm_s24le' and probe['bits_per_sample']==24 and probe['channels']==2
    result['exports'][name]={'frames':len(x),'quantization_max_error':error,'format':probe}
mp=decode(P/'MUSIC_MIX_V2C_SPACE.mp3')
assert len(mp)==N and np.isfinite(mp).all() and np.max(abs(mp))<1
result['exports']['MUSIC_MIX_V2C_SPACE.mp3']={'frames':len(mp),'sample_peak_dBFS':float(20*np.log10(np.max(abs(mp))))}
for filename,rows in json.loads((P/'validation.json').read_text())['comparisons'].items():
    comp=decode(P/filename);assert len(comp)==41*SR and np.isfinite(comp).all() and np.max(abs(comp))<1
    measured=[]
    for row in rows:
        m=measure(comp[round(row['start_s']*SR):round(row['end_s']*SR)])
        assert abs(float(m['input_i'])-row['target_LUFS'])<.12
        measured.append({'label':row['label'],'decoded_LUFS':float(m['input_i']),'decoded_dBTP':float(m['input_tp'])})
    assert abs(measured[0]['decoded_LUFS']-measured[1]['decoded_LUFS'])<.12
    result['comparisons'][filename]=measured
master=raw(P/'master.f32')
fold=float(10*np.log10(np.mean(master.mean(1).astype('float64')**2)/np.mean(master.astype('float64')**2)))
assert fold>-.7;result['master_mono_fold_dB']=fold
result['status']='PASS';result['limits']='Export integrity and gross stereo checks; subjective placement and reverb quality require user audition.'
(P/'export-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
