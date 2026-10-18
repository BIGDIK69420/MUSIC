"""Read back the deliverables and check format, timing, sum and matched A/B."""
from pathlib import Path
import subprocess, json, re
import numpy as np
O=Path('/workspace/audio-rebuild'); C=Path('/workspace/audio-clean'); N=10285140; SR=48000
def decode(path):
    p=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-acodec','pcm_f32le','-ar','48000','-ac','2','-'],capture_output=True,check=True)
    return np.frombuffer(p.stdout,dtype='float32').reshape(-1,2)
def raw(path):return np.memmap(path,dtype='float32',mode='r').reshape(-1,2)
def measure(x):
    p=subprocess.run(['ffmpeg','-hide_banner','-nostats','-f','f32le','-ar','48000','-ac','2','-i','-','-af','loudnorm=I=-16:TP=-1:LRA=8:print_format=json','-f','null','-'],input=x.astype('float32').tobytes(),capture_output=True,check=True)
    return json.loads(re.search(r'\{\s*"input_i".*?\}',p.stderr.decode(),re.S).group())
result={'exports':{},'comparison':[]}
mapping={'MUSIC_v10_REBUILD.wav':'master.f32','MUSIC_v10_VOCAL.wav':'vocal.f32','MUSIC_v10_VOCAL_CORE.wav':'core.f32'}
for name,source in mapping.items():
    p=O/name; x=decode(p)
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries','stream=codec_name,sample_rate,channels,bits_per_sample','-of','json',str(p)],capture_output=True,text=True,check=True).stdout)['streams'][0]
    assert len(x)==N and np.isfinite(x).all() and np.max(abs(x))<1
    err=float(np.max(abs(x-raw(O/source))))
    assert err<2**-22
    assert probe['codec_name']=='pcm_s24le' and probe['bits_per_sample']==24 and int(probe['sample_rate'])==SR and probe['channels']==2
    result['exports'][name]={'frames':len(x),'duration_s':len(x)/SR,'peak_dBFS':float(20*np.log10(np.max(abs(x)))),'max_quantization_error':err,'format':probe,'bytes':p.stat().st_size}
mp=decode(O/'MUSIC_v10_REBUILD.mp3')
assert len(mp)==N and np.isfinite(mp).all() and np.max(abs(mp))<1
result['exports']['MUSIC_v10_REBUILD.mp3']={'frames':len(mp),'duration_s':len(mp)/SR,'peak_dBFS':float(20*np.log10(np.max(abs(mp))))}
result['sums']={
 'core_plus_fx_max_error':float(np.max(abs(raw(O/'core.f32')+raw(O/'fx.f32')-raw(O/'vocal.f32')))),
 'vocal_plus_v9_beat_max_error':float(np.max(abs(raw(O/'vocal.f32')+raw(C/'beat_clean.f32')-raw(O/'premaster.f32')))),
 'core_L_R_max_difference':float(np.max(abs(raw(O/'core.f32')[:,0]-raw(O/'core.f32')[:,1])))
}
assert max(result['sums'].values())<2e-7
comp=decode(O/'MUSIC_v10_COMPARE.mp3'); settings=json.loads((O/'validation.json').read_text())
assert len(comp)==round(53.5*SR) and np.isfinite(comp).all() and np.max(abs(comp))<1
for row in settings['comparison']:
    x=comp[round(row['start_s']*SR):round(row['end_s']*SR)]; m=measure(x)
    delta=float(m['input_i'])-row['target_LUFS']; assert abs(delta)<.15
    result['comparison'].append({'label':row['label'],'decoded_LUFS':float(m['input_i']),'target_error_LU':delta,'decoded_dBTP':float(m['input_tp'])})
result['status']='PASS: decode, format, length, finite samples, peaks, component sums and comparison loudness.'
(O/'export-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
