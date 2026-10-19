"""V2 candidate: small, signal-guided refinements of the accepted V1 (old V13)."""
from pathlib import Path
import json,re,subprocess,shutil
import numpy as np
from scipy import signal,ndimage

B=Path('/workspace/audio-v13');O=Path('/workspace/audio-v2-candidate')
SR=48000;N=(B/'core_mix.f32').stat().st_size//8;H=240;DT=H/SR;K=(N+H-1)//H
times=(np.arange(K)+.5)*DT
def arr(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def write(x,p):np.asarray(x,dtype='float32').tofile(p)
def interp(v):return np.interp(np.arange(N)/SR,times,v).astype('float32')
def smooth(v,attack,release):
    out=np.empty_like(v);q=float(v[0])
    for i,w in enumerate(v):
        a=np.exp(-DT/(attack if w>q else release));q=a*q+(1-a)*w;out[i]=q
    return out
def power(x,lo,hi):
    sos=signal.butter(2,[lo,hi],fs=SR,btype='bandpass',output='sos')
    z=signal.sosfilt(sos,x);z=np.pad(z,(0,K*H-len(z)))
    return ndimage.gaussian_filter1d(np.mean(z.reshape(K,H)**2,axis=1),1.5)
def peak(freq,q,gain):
    a=10**(gain/40);w=2*np.pi*freq/SR;alpha=np.sin(w)/(2*q)
    b=np.array([1+alpha*a,-2*np.cos(w),1-alpha*a]);d=np.array([1+alpha/a,-2*np.cos(w),1-alpha/a])
    return np.r_[b/d[0],d/d[0]].reshape(1,6)
def raw(src,dst,flt):
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(src),'-af',flt,'-f','f32le',str(dst)],check=True)
    assert dst.stat().st_size==N*8
def measure(p,raw_input=True):
    cmd=['ffmpeg','-hide_banner','-nostats']
    if raw_input:cmd+=['-f','f32le','-ar',str(SR),'-ac','2']
    r=subprocess.run(cmd+['-i',str(p),'-af','loudnorm=I=-12:TP=-1.3:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr,re.S).group())
def gain_stats(before,after,drive):
    x=arr(before);y=arr(after);n=min(len(x),len(y))//48*48
    x=np.asarray(x[:n]).reshape(-1,48,2)*drive;y=np.asarray(y[:n]).reshape(-1,48,2)
    e=np.sum(x*x,axis=(1,2));g=np.sum(x*y,axis=(1,2))/np.maximum(e,1e-16)
    gr=-20*np.log10(np.clip(g[e/96>1e-5],1e-6,1))
    return {'method':'Approximate 1ms least-squares gain, driven input > -50dBFS; includes resampling differences.',
      'gain_reduction_dB_percentiles':{str(p):float(np.percentile(gr,p)) for p in [50,90,95,99,99.9,100]},
      'active_percent_over_3dB':float(100*np.mean(gr>3))}

old=json.loads((B/'validation.json').read_text());ctl=np.load(B/'controls.npz')
act=np.interp(times,ctl['times'],ctl['activity'])
voiced=np.interp(times,ctl['times'],ctl['voiced'])
drydb=np.interp(times,ctl['times'],ctl['drydb'])
entry=np.interp(times,ctl['times'],ctl['entry'])
active=(act>.8)&(times>6)&(times<192)
core=np.array(arr(B/'core_mix.f32'));mid=core.mean(1)

# Smooth only relatively prominent upper-HF episodes; no phoneme classification.
ratio=10*np.log10((power(mid,5000,9500)+1e-18)/(power(mid,700,4000)+1e-18))
edge_target=np.clip((ratio+2)/6,0,1)*np.clip((drydb+46)/8,0,1)
edge=smooth(edge_target,.005,.075)*act
filtered=signal.sosfilt(peak(8000,.8,-.8),core,axis=0).astype('float32')
core+=(filtered-core)*interp(edge)[:,None]
write(core,O/'core_unmatched.f32')
ref=measure(B/'core_mix.f32');cur=measure(O/'core_unmatched.f32')
core_makeup=float(ref['input_i'])-float(cur['input_i'])
raw(O/'core_unmatched.f32',O/'core_mix.f32',f'volume={core_makeup:.7f}dB')

# Support existing quieter sustained doubles; preserve their Mid and delay/pitch.
eligible=(act>.8)&(voiced>.7)
weak_threshold=float(np.percentile(drydb[eligible],40))
weakness=np.clip((weak_threshold+1.5-drydb)/4,0,1)
side_lift=.8*smooth(weakness*voiced*act,.180,.230)*voiced*(1-entry)
double=np.array(arr(B/'doubles.f32'));dm=double.mean(1);ds=(double[:,0]-double[:,1])*.5
ds*=10**(interp(side_lift)/20)
double=np.column_stack([dm+ds,dm-ds]).astype('float32')
write(double,O/'doubles.f32')
fx=double.copy()
for layer in ['echo','shallow','deep']:
    shutil.copyfile(B/(layer+'.f32'),O/(layer+'.f32'));fx+=arr(O/(layer+'.f32'))
write(fx,O/'fx_mix.f32');write(arr(O/'core_mix.f32')+fx,O/'vocal.f32')

# Sparse source repair avoids dragging the entire mix at accompaniment-led peaks.
events=json.loads(Path('/workspace/audio-v2-review-master/peak-candidates.json').read_text())
dip=np.zeros(N,dtype='float32')
for event in events['candidates']:
    if not event['candidate']:continue
    center=event['beat_actual_sample_peak_time_s']
    amount=min(.8,event['suggested_maximum_dip_dB'])
    start=max(0,int((center-.008)*SR));end=min(N,int((center+.354)*SR))
    t=np.arange(start,end)/SR-center
    # Start 8ms early, 5ms raised-cosine ramp, hold through +4ms, 50ms decay.
    ramp=.5-.5*np.cos(np.pi*np.clip((t+.008)/.005,0,1))
    pulse=amount*ramp*np.exp(-np.maximum(t-.004,0)/.050)
    # Smoothly truncate the residual during the final 50ms (over six constants).
    tail=.5+.5*np.cos(np.pi*np.clip((t-.304)/.050,0,1))
    pulse*=tail
    dip[start:end]=np.maximum(dip[start:end],pulse.astype('float32'))
dip=ndimage.gaussian_filter1d(dip,SR*.0005)
beat=np.array(arr(B/'beat.f32'))*10**(-dip[:,None]/20)
write(beat,O/'beat.f32');write(beat+arr(O/'vocal.f32'),O/'premaster.f32')
np.savez(O/'controls.npz',times=times,activity=act,voiced=voiced,drydb=drydb,entry=entry,
         hf_ratio=ratio,edge=edge,side_lift_dB=side_lift,
         beat_dip_times=(np.arange((N+47)//48)+.5)*.001,
         beat_dip_dB=np.interp((np.arange((N+47)//48)+.5)*48,np.arange(N),dip))
dip.tofile(O/'beat_dip_dB.f32')
print('PREMASTER_READY',json.dumps({'core_makeup_dB':core_makeup,'weak_threshold_dBFS':weak_threshold,
      'side_lift_above_025dB_s':float(np.sum(side_lift>.25)*DT),'edge_above_025dB_s':float(np.sum(.8*edge>.25)*DT),
      'beat_dip_above_01dB_s':float(np.sum(dip>.1)/SR)}),flush=True)

target=float(old['master']['WAV_LUFS']);prem=measure(O/'premaster.f32')
gain=target-float(prem['input_i']);passes=[]
for attempt in range(6):
    rendered_gain=gain
    raw(O/'premaster.f32',O/'master.f32',f'volume={rendered_gain:.7f}dB,aresample=192000,alimiter=limit={10**(-1.4/20):.10f}:attack=5:release=80:level=0:latency=1,aresample=48000')
    m=measure(O/'master.f32');delta=target-float(m['input_i'])
    passes.append({'gain_dB':rendered_gain,'LUFS':float(m['input_i']),'dBTP':float(m['input_tp'])})
    if abs(delta)<.035:break
    gain+=delta
stats=gain_stats(O/'premaster.f32',O/'master.f32',10**(rendered_gain/20))
assert abs(float(m['input_i'])-target)<.08 and float(m['input_tp'])<-1.1
assert stats['gain_reduction_dB_percentiles']['95']<2.1 and stats['active_percent_over_3dB']<1.8
master=arr(O/'master.f32');assert len(master)==N and np.isfinite(master).all() and np.max(abs(master))<1
mono=float(10*np.log10(np.mean(master.mean(1)**2)/np.mean(master**2)));assert mono>-.8
for suffix,path in [('',O/'master.f32'),('_VOCAL',O/'vocal.f32'),('_VOCAL_CORE',O/'core_mix.f32'),('_VOCAL_FX',O/'fx_mix.f32'),('_BEAT',O/'beat.f32')]:
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(path),'-c:a','pcm_s24le',str(O/('MUSIC_MIX_V2_CANDIDATE'+suffix+'.wav'))],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(O/'MUSIC_MIX_V2_CANDIDATE.wav'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_MIX_V2_CANDIDATE.mp3')],check=True)
mp=measure(O/'MUSIC_MIX_V2_CANDIDATE.mp3',False);assert float(mp['input_tp'])<-.5

result={'status':'candidate_for_user_audition','base':'Formal V1, identical to historical V13; no retuning or formant shifting.',
 'core':{'bell_Hz':8000,'Q':.8,'max_cut_dB':.8,'detector_bands_Hz':[[5000,9500],[700,4000]],'ratio_thresholds_dB':[-2,4],
         'attack_ms':5,'release_ms':75,'core_makeup_dB':core_makeup,'edge_above_025dB_s':float(np.sum(.8*edge>.25)*DT),
         'edge_dose_active_percentiles':{str(p):float(np.percentile(edge[active],p)) for p in [50,90,95,99]}},
 'doubles':{'max_extra_side_dB':.8,'weak_dry_threshold_dBFS':weak_threshold,'attack_ms':180,'release_ms':230,
            'actual_maximum_extra_side_dB':float(np.max(side_lift)),'side_lift_above_025dB_s':float(np.sum(side_lift>.25)*DT),
            'mid':'preserved','timing_and_pitch':'preserved','other_returns':'unchanged'},
 'beat_repair':{'events':events['event_count_after_gates'],'peak_center_source':'peak-candidates.json',
                'maximum_dip_dB':float(np.max(dip)),'lookahead_ms':8,'ramp_ms':5,'hold_through_after_peak_ms':4,
                'release_time_constant_ms':50,'smooth_tail_end_ms':354,'beat_dip_above_01dB_s':float(np.sum(dip>.1)/SR),
                'stereo':'linked scalar gain, no frequency split'},
 'master':{'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),'MP3_LUFS':float(mp['input_i']),
           'MP3_dBTP':float(mp['input_tp']),'limiter':stats,'passes':passes,'mono_fold_energy_dB':mono,'duration_seconds':N/SR},
 'limitations':'No subjective audition. This is a small refinement of an approved sound, not voice identity replication or proof of commercial-record quality. Estimated reference stems were analysed only, never mixed into outputs.'}
(O/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
shutil.copyfile('/workspace/audio-v2-review-master/peak-candidates.json',O/'peak-candidates.json')
print('COMPLETE',json.dumps(result),flush=True)
