"""Validate the encoded comparison and exported WAV format."""
from pathlib import Path
import json,re,subprocess
import numpy as np
P=Path('/workspace/audio-v11');SR=48000
v=json.loads((P/'validation.json').read_text())
r=subprocess.run(['ffmpeg','-v','error','-i',str(P/'MUSIC_v11_COMPARE.mp3'),'-f','f32le','-ac','2','-ar',str(SR),'-'],capture_output=True,check=True)
x=np.frombuffer(r.stdout,dtype='float32').reshape(-1,2)
assert len(x)==round(53.5*SR) and np.isfinite(x).all() and np.max(abs(x))<1
result={'comparison_seconds':len(x)/SR,'segments':[],'WAV_formats':{}}
for row in v['comparison']:
    z=x[round(row['start_s']*SR):round(row['end_s']*SR)]
    q=subprocess.run(['ffmpeg','-hide_banner','-nostats','-f','f32le','-ar',str(SR),'-ac','2','-i','-',
        '-af','loudnorm=I=-16:TP=-1.3:LRA=8:print_format=json','-f','null','-'],input=z.tobytes(),capture_output=True,check=True)
    m=json.loads(re.search(r'\{\s*"input_i".*?\}',q.stderr.decode(),re.S).group())
    assert abs(float(m['input_i'])-row['target_LUFS'])<.12
    result['segments'].append({'label':row['label'],'decoded_LUFS':float(m['input_i']),'decoded_dBTP':float(m['input_tp'])})
for p in sorted(P.glob('MUSIC*.wav')):
    probe=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','a:0','-show_entries',
        'stream=codec_name,sample_rate,channels,bits_per_sample','-of','json',str(p)],capture_output=True,text=True,check=True).stdout)['streams'][0]
    assert probe['codec_name']=='pcm_s24le' and int(probe['sample_rate'])==SR and probe['bits_per_sample']==24 and probe['channels']==2
    result['WAV_formats'][p.name]=probe
result['status']='PASS'
(P/'comparison-check.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
