"""Master and export V2C; equal-loudness comparisons retain source timing."""
from pathlib import Path
import json,re,subprocess
import numpy as np

P=Path('/workspace/audio-v2c-space');B=Path('/workspace/audio-v2b-balance');V=Path('/workspace/audio-v2-candidate')
SR=48000;N=10285140
def arr(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def write(x,p):np.asarray(x,dtype='float32').tofile(p)
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

target=-11.58;gain=5.03;passes=[]
for i in range(5):
    rendered_gain=gain
    process(P/'premaster.f32',P/'master.f32',f'volume={rendered_gain:.7f}dB,aresample=192000,alimiter=limit={10**(-1.4/20):.10f}:attack=5:release=80:level=0:latency=1,aresample=48000')
    m=measure(P/'master.f32');delta=target-float(m['input_i'])
    passes.append({'drive_dB':rendered_gain,'LUFS':float(m['input_i']),'dBTP':float(m['input_tp'])})
    print('MASTER_PASS',passes[-1],flush=True)
    if abs(delta)<.035:break
    gain+=delta
stats=gr_stats(P/'premaster.f32',P/'master.f32',10**(rendered_gain/20))
assert abs(float(m['input_i'])-target)<.08 and float(m['input_tp'])<-1.1
assert stats['percentiles_dB']['95']<2.2 and stats['active_percent_over_3dB']<2
for suffix,raw in [('', 'master.f32'),('_VOCAL','vocal.f32'),('_VOCAL_FX','fx_mix.f32'),('_REVERB','reverb.f32')]:
    x=arr(P/raw);assert len(x)==N and np.isfinite(x).all() and np.max(abs(x))<1
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(P/raw),'-c:a','pcm_s24le',str(P/('MUSIC_MIX_V2C_SPACE'+suffix+'.wav'))],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(P/'MUSIC_MIX_V2C_SPACE.wav'),'-c:a','libmp3lame','-b:a','320k',str(P/'MUSIC_MIX_V2C_SPACE.mp3')],check=True)
mp=measure(P/'MUSIC_MIX_V2C_SPACE.mp3',False);assert float(mp['input_tp'])<-.5

comparisons={}
for kind,sources,target_lufs in [('MIX',[B/'master.f32',P/'master.f32'],-16),('VOCAL',[V/'vocal.f32',P/'vocal.f32'],-20)]:
    parts=[];rows=[]
    for label,src in zip(['V2B','V2C'],sources):
        segs=[]
        for j,(a,b) in enumerate([(58,72),(98,104)]):
            x=np.array(arr(src)[a*SR:b*SR]);fade=np.linspace(0,1,384)
            x[:384]*=fade[:,None];x[-384:]*=fade[::-1,None]
            if j:segs.append(np.zeros((SR//4,2),'float32'))
            segs.append(x)
        x=np.concatenate(segs);tmp=P/f'compare_{kind}_{label}.f32';write(x,tmp)
        gain_db=target_lufs-float(measure(tmp)['input_i']);x*=10**(gain_db/20)
        start=sum(len(s) for s in parts)/SR
        rows.append({'label':label,'start_s':start,'end_s':start+len(x)/SR,'source_intervals_s':[[58,72],[98,104]],'target_LUFS':target_lufs,'gain_dB':gain_db})
        parts.extend([x,np.zeros((SR//2,2),'float32')])
    comparison=np.concatenate(parts[:-1]);assert len(comparison)==41*SR and np.max(abs(comparison))<1
    tmp=P/f'comparison_{kind}.f32';write(comparison,tmp)
    filename=f'MUSIC_V2B_TO_V2C_{kind}_COMPARE.mp3'
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(tmp),'-c:a','libmp3lame','-b:a','320k',str(P/filename)],check=True)
    comparisons[filename]=rows
result={'status':'space_revision_for_user_audition','master':{'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),
 'MP3_LUFS':float(mp['input_i']),'MP3_dBTP':float(mp['input_tp']),'passes':passes,'limiter':stats,'duration_seconds':N/SR},
 'comparisons':comparisons,'limitations':'Technical verification does not establish subjective naturalness or professional vocal placement.'}
(P/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
