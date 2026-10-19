from pathlib import Path
import json,re,subprocess,hashlib
import numpy as np
from scipy import signal
from scipy.io import wavfile

P=Path('/workspace/audio-v2-candidate');B=Path('/workspace/audio-v13');SR=48000;N=10285140
def arr(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def db(x):return float(20*np.log10(max(float(x),1e-15)))
def decode(p):
 r=subprocess.run(['ffmpeg','-v','error','-i',str(p),'-f','f32le','-ar',str(SR),'-ac','2','-'],check=True,capture_output=True)
 return np.frombuffer(r.stdout,dtype='float32').reshape(-1,2)
def loudness(x):
 r=subprocess.run(['ffmpeg','-hide_banner','-nostats','-f','f32le','-ar',str(SR),'-ac','2','-i','-',
  '-af','loudnorm=I=-16:TP=-1.3:LRA=8:print_format=json','-f','null','-'],input=x.astype('float32').tobytes(),capture_output=True,check=True)
 return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr.decode(),re.S).group())
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
out={'exports':{},'comparison':[],'routing':{},'base_preservation':[]}
mapping={'MUSIC_MIX_V2_CANDIDATE.wav':'master.f32','MUSIC_MIX_V2_CANDIDATE_VOCAL.wav':'vocal.f32',
 'MUSIC_MIX_V2_CANDIDATE_VOCAL_CORE.wav':'core_mix.f32','MUSIC_MIX_V2_CANDIDATE_VOCAL_FX.wav':'fx_mix.f32',
 'MUSIC_MIX_V2_CANDIDATE_BEAT.wav':'beat.f32'}
for name,raw in mapping.items():
 sr,x=wavfile.read(P/name);assert x.dtype==np.int32
 x=x.astype('float32')/2147483648
 probe=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries',
  'stream=codec_name,sample_rate,channels,bits_per_sample','-of','json',str(P/name)],capture_output=True,text=True,check=True).stdout)['streams'][0]
 error=float(np.max(abs(x-arr(P/raw))))
 assert sr==SR and len(x)==N and np.isfinite(x).all() and np.max(abs(x))<1 and error<3e-7
 assert probe['codec_name']=='pcm_s24le' and probe['bits_per_sample']==24 and probe['channels']==2
 out['exports'][name]={'format':probe,'frames':len(x),'sample_peak_dBFS':db(np.max(abs(x))),'quantization_error':error}
mp=decode(P/'MUSIC_MIX_V2_CANDIDATE.mp3');assert len(mp)==N and np.isfinite(mp).all() and np.max(abs(mp))<1
tp=db(max(float(np.max(abs(signal.resample_poly(mp[max(0,i-SR//10):min(N,i+20*SR+SR//10)],4,1,axis=0)))) for i in range(0,N,20*SR)))
assert tp<-.5
out['exports']['MUSIC_MIX_V2_CANDIDATE.mp3']={'frames':len(mp),'sample_peak_dBFS':db(np.max(abs(mp))),'independent_4x_peak_dBFS':tp}
out['routing']['core_plus_fx_max_error']=float(np.max(abs(arr(P/'core_mix.f32')+arr(P/'fx_mix.f32')-arr(P/'vocal.f32'))))
out['routing']['vocal_plus_beat_max_error']=float(np.max(abs(arr(P/'vocal.f32')+arr(P/'beat.f32')-arr(P/'premaster.f32'))))
assert max(out['routing'].values())<5e-7
for layer in ['echo','shallow','deep']:
 assert digest(P/(layer+'.f32'))==digest(B/(layer+'.f32'))
out['unchanged_returns']=['echo','shallow','deep']

comp=decode(P/'MUSIC_V1_TO_V2_CANDIDATE_COMPARE.mp3')
assert len(comp)==70*SR and np.isfinite(comp).all() and np.max(abs(comp))<1
for row in json.loads((P/'comparison.json').read_text()):
 m=loudness(comp[round(row['start_s']*SR):round(row['end_s']*SR)])
 assert abs(float(m['input_i'])-row['target_LUFS'])<.12
 out['comparison'].append({'label':row['label'],'decoded_LUFS':float(m['input_i']),'decoded_dBTP':float(m['input_tp'])})
base=Path('/workspace/MUSIC/releases/mix-experiment-v1')
for row in json.loads((base/'release.json').read_text())['audio']:
 sha=digest(base/row['file']);assert sha==row['sha256']
 out['base_preservation'].append({'file':row['file'],'sha256':sha,'unchanged':True})
out['status']='PASS';out['scope']='Export integrity, routing, comparison loudness and preservation of the approved V1. Subjective musical suitability remains for user audition.'
(P/'export-check.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'status':out['status'],'MP3_4x_peak_dBFS':tp,'comparison':out['comparison'],'base_files_unchanged':len(out['base_preservation'])},indent=2))
