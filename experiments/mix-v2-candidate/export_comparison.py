from pathlib import Path
import json,re,subprocess
import numpy as np

P=Path('/workspace/audio-v2-candidate');B=Path('/workspace/audio-v13');SR=48000
def arr(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def measure(p):
 r=subprocess.run(['ffmpeg','-hide_banner','-nostats','-f','f32le','-ar',str(SR),'-ac','2','-i',str(p),
 '-af','loudnorm=I=-16:TP=-1.3:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
 return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr,re.S).group())
groups=[('V1_MIX',B/'master.f32',[(38,50),(58,70)],-16),
        ('V2_CANDIDATE_MIX',P/'master.f32',[(38,50),(58,70)],-16),
        ('V1_VOCAL',B/'vocal.f32',[(120,130)],-20),
        ('V2_CANDIDATE_VOCAL',P/'vocal.f32',[(120,130)],-20)]
parts=[];rows=[]
for name,path,intervals,level in groups:
 segments=[]
 for i,(start,end) in enumerate(intervals):
  x=np.array(arr(path)[start*SR:end*SR]);fade=np.linspace(0,1,384)
  x[:384]*=fade[:,None];x[-384:]*=fade[::-1,None]
  if i:segments.append(np.zeros((SR//4,2),'float32'))
  segments.append(x)
 x=np.concatenate(segments);tmp=P/(name+'.f32');x.tofile(tmp)
 gain=level-float(measure(tmp)['input_i']);x*=10**(gain/20);assert np.max(abs(x))<1
 at=sum(len(p) for p in parts)/SR
 rows.append({'label':name,'start_s':at,'end_s':at+len(x)/SR,'source_intervals_s':intervals,'target_LUFS':level,'gain_dB':gain})
 parts.extend([x,np.zeros((SR//2,2),'float32')])
out=np.concatenate(parts[:-1]);assert len(out)==70*SR
out.tofile(P/'comparison.f32')
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(P/'comparison.f32'),
                '-c:a','libmp3lame','-b:a','320k',str(P/'MUSIC_V1_TO_V2_CANDIDATE_COMPARE.mp3')],check=True)
(P/'comparison.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
