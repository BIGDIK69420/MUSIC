"""Independent output and preservation checks; no subjective claims."""
import json, subprocess, re
from pathlib import Path
import numpy as np
from scipy import signal

O=Path('/workspace/audio-unbox');V=Path('/workspace/audio-clarity');sr=48000
def array(p): return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def measure(p,raw=True):
    cmd=['ffmpeg','-hide_banner','-nostats']
    if raw:cmd+=['-f','f32le','-ar','48000','-ac','2']
    cmd+=['-i',str(p),'-af','loudnorm=I=-16:TP=-1.2:LRA=8:print_format=json','-f','null','-']
    r=subprocess.run(cmd,capture_output=True,text=True,check=True)
    return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr,re.S).group())
old=array(V/'vocal_mix_level.f32');N=len(old)
refmix=array(V/'premaster.f32');reports={}
dry=np.load('/workspace/audio-analysis/dry_rms.npy')
active=np.interp(np.arange(N)/sr,np.arange(len(dry))*.04+.02,dry)>10**(-38/20)
quiet=np.interp(np.arange(N)/sr,np.arange(len(dry))*.04+.02,dry)<10**(-48/20)
bands=[(150,280),(350,650),(650,1050),(1200,1800),(2500,5000),(5000,10000)]
def bands_energy(x):
    m=x.mean(axis=1)
    e={}
    for lo,hi in bands:
        z=signal.sosfilt(signal.butter(3,[lo,hi],fs=sr,btype='bandpass',output='sos'),m)
        e[f'{lo}-{hi}']=float(np.mean(z[active]**2))
    return e
e0=bands_energy(old)
for name in ['MUSIC_v6_OPEN','MUSIC_v6_DRIER']:
    x=array(O/(name+'_vocal.f32'));master=array(O/(name+'.f32'));pre=array(O/(name+'_premaster.f32'))
    assert x.shape==old.shape==master.shape
    assert np.isfinite(x).all() and np.isfinite(master).all()
    err=0.
    for st in range(0,N,sr*10):
        en=min(N,st+sr*10)
        err=max(err,float(np.max(abs((pre[st:en]-x[st:en])-(refmix[st:en]-old[st:en])))))
    assert err<2e-7
    e=bands_energy(x);delta={k:float(10*np.log10(e[k]/e0[k])) for k in e}
    # Preserve body and intelligibility; this does not judge whether the subjective boxiness improved.
    assert delta['150-280']>-.9,(name,'body',delta)
    assert delta['2500-5000']>-.75,(name,'clarity',delta)
    assert delta['350-650']<-.2 and delta['650-1050']<-.2,(name,'target effect',delta)
    # Weak-tail preservation: inspect meaningful frames, not silent numerical noise.
    block=1920;L=N//block*block
    bx=np.sqrt(np.mean(x[:L].reshape(-1,block,2)**2,axis=(1,2)))
    bo=np.sqrt(np.mean(old[:L].reshape(-1,block,2)**2,axis=(1,2)))
    frame_dry=dry[:len(bx)]
    weak=(frame_dry>10**(-50/20))&(frame_dry<10**(-38/20))&(bo>10**(-45/20))
    d=20*np.log10(np.maximum(bx[weak],1e-12)/bo[weak])
    assert np.percentile(d,1)>-5,(name,'weak syllables',np.percentile(d,[1,50,99]))
    wave=json.loads(subprocess.run(['ffprobe','-v','error','-show_entries','stream=sample_rate,channels,bits_per_sample,duration','-of','json',str(O/(name+'.wav'))],capture_output=True,text=True,check=True).stdout)['streams'][0]
    assert wave['sample_rate']=='48000' and wave['channels']==2 and wave['bits_per_sample']==24
    assert abs(float(wave['duration'])-N/sr)<1/sr
    reports[name]={'active_mid_band_energy_delta_vs_V4_dB':delta,'weak_vocal_frame_delta_dB_percentiles':{str(q):float(np.percentile(d,q)) for q in [1,10,50,90,99]},'unchanged_premaster_accompaniment_max_absolute_residual':err,'format':wave,'master_adjacent_sample_jump_p9999':float(np.percentile(abs(np.diff(master,axis=0)),99.99))}

# A compact fixed-order comparison, individually loudness matched, same passage.
items=[('V4',V/'master.f32'),('V6_OPEN',O/'MUSIC_v6_OPEN.f32'),('V6_DRIER',O/'MUSIC_v6_DRIER.f32')]
comparison=[];comp_report=[]
for label,path in items:
    clip=np.array(array(path)[82*sr:102*sr]);tmp=O/('compare_'+label+'.f32');clip.tofile(tmp)
    loud=measure(tmp);gain=-16-float(loud['input_i']);clip*=10**(gain/20)
    assert abs(clip).max()<.97
    fade=np.linspace(0,1,int(.008*sr),dtype='float32')
    clip[:len(fade)]*=fade[:,None];clip[-len(fade):]*=fade[::-1,None]
    start=sum(len(c) for c in comparison)/sr
    comparison.append(clip);comparison.append(np.zeros((sr//2,2),dtype='float32'))
    comp_report.append({'label':label,'start_s':start,'end_s':start+20,'gain_dB':gain,'clip_LUFS_before':float(loud['input_i']),'target_LUFS':-16})
np.concatenate(comparison[:-1]).tofile(O/'comparison.f32')
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(O/'comparison.f32'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v6_COMPARE.mp3')],check=True)
reports['comparison']=comp_report
(O/'quality-check.json').write_text(json.dumps(reports,indent=2))
print(json.dumps(reports,indent=2))
