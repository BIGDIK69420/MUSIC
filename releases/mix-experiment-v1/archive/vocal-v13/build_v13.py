"""V13: context-sensitive vocal placement and phrase-entry finishing of V12."""
from pathlib import Path
import json,re,subprocess
import numpy as np
from scipy import signal,ndimage

B=Path('/workspace/audio-v12');O=Path('/workspace/audio-v13');C=Path('/workspace/audio-clean')
SR=48000;N=(B/'core_mix.f32').stat().st_size//8;H=480;K=(N+H-1)//H
times=(np.arange(K)+.5)*H/SR;old=json.loads((B/'validation.json').read_text())
def arr(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def write(x,p):np.asarray(x,dtype='float32').tofile(p)
def rms(x):return float(np.sqrt(np.mean(np.asarray(x,dtype='float64')**2)))
def interp(v):return np.interp(np.arange(N)/SR,times,v).astype('float32')
def raw(src,dst,flt):
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(src),'-af',flt,'-f','f32le',str(dst)],check=True)
    assert dst.stat().st_size==N*8
def measure(p,raw_input=True):
    cmd=['ffmpeg','-hide_banner','-nostats']
    if raw_input:cmd+=['-f','f32le','-ar',str(SR),'-ac','2']
    r=subprocess.run(cmd+['-i',str(p),'-af','loudnorm=I=-12:TP=-1.3:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr,re.S).group())
def smooth(v,attack,release):
    out=np.empty_like(v);q=float(v[0])
    for i,w in enumerate(v):
        a=np.exp(-.01/(attack if w>q else release));q=a*q+(1-a)*w;out[i]=q
    return out
def peak(freq,q,gain):
    a=10**(gain/40);w=2*np.pi*freq/SR;alpha=np.sin(w)/(2*q)
    b=np.array([1+alpha*a,-2*np.cos(w),1-alpha*a]);d=np.array([1+alpha/a,-2*np.cos(w),1-alpha/a])
    return np.r_[b/d[0],d/d[0]].reshape(1,6)
def gain_stats(before,after,drive):
    x=arr(before);y=arr(after);n=min(len(x),len(y))//48*48
    x=np.asarray(x[:n]).reshape(-1,48,2)*drive;y=np.asarray(y[:n]).reshape(-1,48,2)
    e=np.sum(x*x,axis=(1,2));g=np.sum(x*y,axis=(1,2))/np.maximum(e,1e-16)
    gr=-20*np.log10(np.clip(g[e/96>1e-5],1e-6,1))
    return {'method':'Approximate 1 ms least-squares gain, input > -50 dBFS; includes resampling differences.',
        'gain_reduction_dB_percentiles':{str(p):float(np.percentile(gr,p)) for p in [50,90,95,99,99.9,100]},
        'active_percent_over_3dB':float(100*np.mean(gr>3))}

ctl=np.load(B/'controls.npz');competition=np.load(O/'competition.npz')
assert len(competition['times'])==K and np.max(abs(competition['times']-times))<1e-6
drydb=ctl['drydb'];act=ctl['activity'];active_frames=(drydb>-38)&(times>6)&(times<192)
active=interp(active_frames.astype(float))>.9

# The existing 900–1600 Hz overlap measurement drives a bounded accompaniment move.
# Its threshold is an operating choice, not a proved psychoacoustic masking threshold.
dose=smooth(competition['dose'],.035,.20)
beat=np.array(arr(C/'beat_clean.f32'));bm=beat.mean(1);bs=(beat[:,0]-beat[:,1])*.5
cut=signal.sosfilt(peak(1150,1.05,-1.5),bm).astype('float32')
bm+=(cut-bm)*interp(dose)
write(np.column_stack([bm+bs,bm-bs]),O/'beat.f32')

# Small slow rides on voiced parts that coincide with stronger competition.
# Pitch/periodicity data select activity only; there is no pitch processing in V13.
pitch=np.load('/workspace/audio-v10-pitch/comparison.npz')
confidence=np.clip((pitch['mixed_periodicity']-.45)/.25,0,1)*(pitch['mixed']>65)
confidence=np.interp(times,pitch['t'],confidence)
need=ndimage.gaussian_filter1d(dose,12)*confidence
ride=smooth(np.clip(.65*need,0,.65),.14,.25)*act
for i in range(1,K):ride[i]=np.clip(ride[i],ride[i-1]-.018,ride[i-1]+.018)
for i in range(K-2,-1,-1):ride[i]=np.clip(ride[i],ride[i+1]-.018,ride[i+1]+.018)
core=np.array(arr(B/'core_mix.f32'));core*=10**(interp(ride)[:,None]/20)
write(core,O/'core_unmatched.f32')
ref=measure(B/'core_mix.f32');cur=measure(O/'core_unmatched.f32')
core_makeup=float(ref['input_i'])-float(cur['input_i'])
raw(O/'core_unmatched.f32',O/'core_mix.f32',f'volume={core_makeup:.7f}dB')

# Briefly move the existing returns back at phrase entries, keeping phrase-end richness.
onsets=json.loads((O/'onset_candidates.json').read_text())['times_s']
entry=np.zeros(K)
for onset in onsets:
    relative=times-(onset-.020)
    ramp=np.clip(relative/.020,0,1)
    decay=np.exp(-np.maximum(relative-.120,0)/.100)
    pulse=ramp*decay; pulse[(relative<0)|(relative>.620)]=0
    entry=np.maximum(entry,pulse)
entry=ndimage.gaussian_filter1d(entry,.7);entry_samples=interp(entry)
doubles=np.array(arr(B/'doubles.f32'))
echo=np.array(arr(B/'echo.f32'))*10**(-1.5*entry_samples[:,None]/20)
shallow=np.array(arr(B/'shallow.f32'))*10**(-.6*entry_samples[:,None]/20)
deep=np.array(arr(B/'deep.f32'))*10**(-2.0*entry_samples[:,None]/20)
fx=doubles+echo+shallow+deep
for name,x in [('doubles',doubles),('echo',echo),('shallow',shallow),('deep',deep),('fx_mix',fx)]:write(x,O/(name+'.f32'))
write(arr(O/'core_mix.f32')+fx,O/'vocal.f32')
write(arr(O/'beat.f32')+arr(O/'vocal.f32'),O/'premaster.f32')
print('PREMASTER_READY',json.dumps({'core_makeup_dB':core_makeup,'phrase_entries':len(onsets),'ride_above_025dB_s':float(np.sum(ride>.25)*.01)}),flush=True)

target=float(old['master']['WAV_LUFS']);prem=measure(O/'premaster.f32');gain=target-float(prem['input_i']);passes=[]
for attempt in range(6):
    rendered_gain=gain
    raw(O/'premaster.f32',O/'master.f32',f'volume={rendered_gain:.7f}dB,aresample=192000,alimiter=limit={10**(-1.4/20):.10f}:attack=5:release=80:level=0:latency=1,aresample=48000')
    m=measure(O/'master.f32');delta=target-float(m['input_i'])
    passes.append({'gain_dB':rendered_gain,'LUFS':float(m['input_i']),'dBTP':float(m['input_tp'])})
    if abs(delta)<.04:break
    gain+=delta
stats=gain_stats(O/'premaster.f32',O/'master.f32',10**(rendered_gain/20))
assert abs(float(m['input_i'])-target)<.08 and float(m['input_tp'])<-1.1
assert stats['gain_reduction_dB_percentiles']['95']<2.8 and stats['active_percent_over_3dB']<3
master=arr(O/'master.f32');assert len(master)==N and np.isfinite(master).all() and np.max(abs(master))<1
mono=float(10*np.log10(np.mean(master.mean(1)**2)/np.mean(master**2)));assert mono>-.8
for name,path in [('MUSIC_v13_FINISH',O/'master.f32'),('MUSIC_v13_VOCAL',O/'vocal.f32'),('MUSIC_v13_VOCAL_CORE',O/'core_mix.f32'),('MUSIC_v13_VOCAL_FX',O/'fx_mix.f32'),('MUSIC_v13_BEAT',O/'beat.f32')]:
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(path),'-c:a','pcm_s24le',str(O/(name+'.wav'))],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(O/'MUSIC_v13_FINISH.wav'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v13_FINISH.mp3')],check=True)
mp=measure(O/'MUSIC_v13_FINISH.mp3',False);assert float(mp['input_tp'])<-.5

# Contrast a quieter rhythmic passage and a sustained passage, then the same solo phrase.
parts=[];comparison=[]
groups=[('V12_MIX',B/'master.f32',[(38,50),(60,72)],-16),('V13_MIX',O/'master.f32',[(38,50),(60,72)],-16),
        ('V12_VOCAL',B/'vocal.f32',[(38,48)],-20),('V13_VOCAL',O/'vocal.f32',[(38,48)],-20)]
for label,path,intervals,level in groups:
    segments=[]
    for i,(start,end) in enumerate(intervals):
        x=np.array(arr(path)[start*SR:end*SR]);fade=np.linspace(0,1,384);x[:384]*=fade[:,None];x[-384:]*=fade[::-1,None]
        if i:segments.append(np.zeros((SR//4,2),'float32'))
        segments.append(x)
    x=np.concatenate(segments);p=O/(label+'.f32');write(x,p);lm=measure(p);g=level-float(lm['input_i']);x*=10**(g/20);assert np.max(abs(x))<.99
    at=sum(len(a) for a in parts)/SR
    comparison.append({'label':label,'start_s':at,'end_s':at+len(x)/SR,'source_intervals_s':intervals,'target_LUFS':level,'gain_dB':g})
    parts.extend([x,np.zeros((SR//2,2),'float32')])
write(np.concatenate(parts[:-1]),O/'comparison.f32')
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(O/'comparison.f32'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v13_COMPARE.mp3')],check=True)
np.savez(O/'controls.npz',times=times,activity=act,voiced=ctl['voiced'],drydb=drydb,ride=ride,beat_dose=dose,entry=entry)
result={'basis':'V12 core, layers and pitch/timing retained; accompaniment Mid receives bounded context-dependent relief. No additional global vocal EQ, widening or retuning.',
 'accompaniment':{'detector_band_Hz':[900,1600],'bell_Hz':1150,'Q':1.05,'maximum_cut_dB':1.5,'attack_ms':35,'release_ms':200,'side':'preserved','gain_makeup_dB':0,'active_dose_percentiles':{str(q):float(np.percentile(dose[active_frames],q)) for q in [50,75,90,95,99]}},
 'vocal':{'maximum_local_lift_dB':.65,'attack_ms':140,'release_ms':250,'maximum_slew_dB_per_s':1.8,'core_loudness_target':'same as V12 CORE','core_makeup_dB':core_makeup,'active_lift_percentiles_dB':{str(q):float(np.percentile(ride[active_frames],q)) for q in [50,75,90,95,99]},'lift_above_025dB_s':float(np.sum(ride>.25)*.01)},
 'phrase_entries':{'candidates_s':onsets,'early_start_ms':20,'ramp_ms':20,'hold_until_ms_from_early_start':120,'release_time_constant_ms':100,'maximum_extra_return_duck_dB':{'echo':1.5,'deep':2.0,'shallow':.6},'double_change':'none'},
 'master':{'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),'MP3_LUFS':float(mp['input_i']),'MP3_dBTP':float(mp['input_tp']),'limiter':stats,'passes':passes,'mono_fold_energy_dB':mono,'duration_seconds':N/SR},
 'comparison':comparison,'limitations':'No subjective audition; technical measures do not establish professional-record quality. Band competition and phrase entries are signal-based operating cues, not proved masking or recognized lyrics. CORE retains previously printed effects.'}
(O/'validation.json').write_text(json.dumps(result,indent=2));print('COMPLETE',json.dumps(result),flush=True)
