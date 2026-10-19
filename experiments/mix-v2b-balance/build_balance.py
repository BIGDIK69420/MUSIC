"""V2B balance revision: accompaniment +1.5 dB relative to the unchanged V2 vocal."""
from pathlib import Path
import json,re,subprocess,hashlib
import numpy as np

B=Path('/workspace/audio-v2-candidate');O=Path('/workspace/audio-v2b-balance')
SR=48000;N=(B/'vocal.f32').stat().st_size//8;LIFT=1.5
def arr(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def write(x,p):np.asarray(x,dtype='float32').tofile(p)
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def measure(p,raw=True):
 cmd=['ffmpeg','-hide_banner','-nostats']
 if raw:cmd+=['-f','f32le','-ar',str(SR),'-ac','2']
 r=subprocess.run(cmd+['-i',str(p),'-af','loudnorm=I=-12:TP=-1.3:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
 return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr,re.S).group())
def process(src,dst,flt):
 subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(src),'-af',flt,'-f','f32le',str(dst)],check=True)
 assert dst.stat().st_size==N*8
def gr_stats(src,dst,drive):
 x=arr(src);y=arr(dst);n=len(x)//48*48
 x=np.asarray(x[:n]).reshape(-1,48,2)*drive;y=np.asarray(y[:n]).reshape(-1,48,2)
 power=np.sum(x*x,axis=(1,2));g=np.sum(x*y,axis=(1,2))/np.maximum(power,1e-16)
 gr=-20*np.log10(np.clip(g[power/96>1e-5],1e-6,1))
 return {'method':'Approximate 1ms least-squares gain; includes resampling differences.',
 'percentiles_dB':{str(p):float(np.percentile(gr,p)) for p in [50,90,95,99,99.9,100]},'active_percent_over_3dB':float(100*np.mean(gr>3))}

old=json.loads((B/'validation.json').read_text());vocal_hash=digest(B/'vocal.f32')
write(arr(B/'beat.f32')*10**(LIFT/20),O/'beat.f32')
write(arr(O/'beat.f32')+arr(B/'vocal.f32'),O/'premaster.f32')
target=float(old['master']['WAV_LUFS']);m=measure(O/'premaster.f32');gain=target-float(m['input_i']);passes=[]
for attempt in range(6):
 rendered_gain=gain
 process(O/'premaster.f32',O/'master.f32',f'volume={rendered_gain:.7f}dB,aresample=192000,alimiter=limit={10**(-1.4/20):.10f}:attack=5:release=80:level=0:latency=1,aresample=48000')
 m=measure(O/'master.f32');delta=target-float(m['input_i'])
 passes.append({'drive_dB':rendered_gain,'LUFS':float(m['input_i']),'dBTP':float(m['input_tp'])})
 if abs(delta)<.035:break
 gain+=delta
assert abs(float(m['input_i'])-target)<.08 and float(m['input_tp'])<-1.1
stats=gr_stats(O/'premaster.f32',O/'master.f32',10**(rendered_gain/20))
assert stats['percentiles_dB']['95']<3 and stats['active_percent_over_3dB']<4
for name,raw in [('MUSIC_MIX_V2B_BALANCE','master.f32'),('MUSIC_MIX_V2B_BEAT','beat.f32')]:
 x=arr(O/raw);assert len(x)==N and np.isfinite(x).all() and np.max(abs(x))<1
 subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(O/raw),'-c:a','pcm_s24le',str(O/(name+'.wav'))],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(O/'MUSIC_MIX_V2B_BALANCE.wav'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_MIX_V2B_BALANCE.mp3')],check=True)
mp=measure(O/'MUSIC_MIX_V2B_BALANCE.mp3',False);assert float(mp['input_tp'])<-.5

parts=[];rows=[]
for label,p in [('V2',B/'master.f32'),('V2B',O/'master.f32')]:
 segs=[]
 for i,(a,b) in enumerate([(38,50),(58,70)]):
  x=np.array(arr(p)[a*SR:b*SR]);fade=np.linspace(0,1,384)
  x[:384]*=fade[:,None];x[-384:]*=fade[::-1,None]
  if i:segs.append(np.zeros((SR//4,2),'float32'))
  segs.append(x)
 x=np.concatenate(segs);tmp=O/(label+'.f32');write(x,tmp)
 compensation=-16-float(measure(tmp)['input_i']);x*=10**(compensation/20)
 at=sum(len(s) for s in parts)/SR
 rows.append({'label':label,'start_s':at,'end_s':at+len(x)/SR,'source_intervals_s':[[38,50],[58,70]],'target_LUFS':-16,'gain_dB':compensation})
 parts.extend([x,np.zeros((SR//2,2),'float32')])
comparison=np.concatenate(parts[:-1]);assert len(comparison)==49*SR and np.max(abs(comparison))<1
write(comparison,O/'comparison.f32')
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(O/'comparison.f32'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_V2_TO_V2B_COMPARE.mp3')],check=True)
assert digest(B/'vocal.f32')==vocal_hash
result={'status':'balance_revision_for_user_audition','base':'V2 candidate',
 'change':{'beat_gain_relative_to_vocal_dB':LIFT,'vocal_processing':'unchanged','new_EQ_or_space_processing':False,
           'vocal_source':'/workspace/audio-v2-candidate/vocal.f32','vocal_source_sha256':vocal_hash},
 'master':{'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),'MP3_LUFS':float(mp['input_i']),
           'MP3_dBTP':float(mp['input_tp']),'passes':passes,'limiter':stats,'duration_seconds':N/SR},
 'comparison':rows,'limitations':'Signal-based mix balance revision. No subjective audition; user decides whether the accompaniment is now sufficiently prominent.'}
(O/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)
