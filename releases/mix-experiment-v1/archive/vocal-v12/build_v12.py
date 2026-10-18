"""V12: refine the user-approved V11 without rebuilding or retuning its lead."""
from pathlib import Path
import json,re,subprocess
import numpy as np
from scipy import signal,ndimage

B=Path('/workspace/audio-v11');O=Path('/workspace/audio-v12');C=Path('/workspace/audio-clean')
SR=48000;N=(B/'core_mix.f32').stat().st_size//8;H=480;K=(N+H-1)//H
times=(np.arange(K)+.5)*H/SR;original=json.loads((B/'validation.json').read_text())
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
def bp(x,lo,hi):return signal.sosfilt(signal.butter(2,[lo,hi],fs=SR,btype='bandpass',output='sos'),x,axis=0).astype('float32')
def power(x,lo,hi):
    y=bp(x,lo,hi);y=np.pad(y,(0,K*H-len(y)))
    return ndimage.gaussian_filter1d(np.mean(y.reshape(K,H).astype('float64')**2,axis=1),3)
def peak(freq,q,gain):
    a=10**(gain/40);w=2*np.pi*freq/SR;alpha=np.sin(w)/(2*q)
    b=np.array([1+alpha*a,-2*np.cos(w),1-alpha*a]);d=np.array([1+alpha/a,-2*np.cos(w),1-alpha/a])
    return np.r_[b/d[0],d/d[0]].reshape(1,6)
def gain_stats(before,after,drive):
    x=arr(before);y=arr(after);n=min(len(x),len(y))//48*48
    x=np.asarray(x[:n]).reshape(-1,48,2)*drive;y=np.asarray(y[:n]).reshape(-1,48,2)
    e=np.sum(x*x,axis=(1,2));g=np.sum(x*y,axis=(1,2))/np.maximum(e,1e-16)
    gr=-20*np.log10(np.clip(g[e/96>1e-5],1e-6,1))
    return {'method':'1 ms least-squares gain relative to driven input; active blocks > -50 dBFS; approximate and includes resampling differences.',
            'gain_reduction_dB_percentiles':{str(p):float(np.percentile(gr,p)) for p in [50,90,95,99,99.9,100]},
            'active_percent_over_3dB':float(100*np.mean(gr>3))}

ctl=np.load(B/'controls.npz');assert len(ctl['times'])==K
act=ctl['activity'];voiced=ctl['voiced'];drydb=ctl['drydb'];activity=interp(act)
active_frames=(drydb>-38)&(times>6)&(times<192);active=interp(active_frames.astype(float))>.9
selected=interp(voiced)>.65
core=np.array(arr(B/'core_mix.f32'));lead=core.mean(1)

# Lift only quieter sustained singing; no change in the tuning or vowel selection.
speech_level=10*np.log10(power(lead,500,4500)+1e-16)
local=ndimage.gaussian_filter1d(speech_level,30)
ride_target=float(np.percentile(local[voiced>.35],60))
ride=np.clip((ride_target-local)*.22,0,.9)*voiced
ride=smooth(ride,.10,.18)*act
ride_samples=interp(ride)

# Increase the already approved V11 nonlinear color slightly, using its isolated component.
color=np.fromfile(B/'harmonic_color_mono.f32',dtype='float32');assert len(color)==N
color_gain=10**((original['core_loudness_compensation_dB']+original['levels']['vocal_post_FX_gain_dB'])/20)
added_color=color*color_gain*(10**(1.5/20)-1)
core+=added_color[:,None]
core*=10**(ride_samples[:,None]/20)

# A bounded edge control, separate from a very small shelf above the sibilant region.
ratio=10*np.log10((power(lead,4800,8500)+1e-16)/(power(lead,1200,4500)+1e-16))
edge_threshold=float(np.percentile(ratio[active_frames],88))
edge=smooth(np.clip((ratio-edge_threshold)/5.5,0,1),.008,.095)*act
cut=signal.sosfilt(peak(6500,.9,-1.2),core,axis=0).astype('float32')
core+=(cut-core)*interp(edge)[:,None]
write(core,O/'core_before_air.f32')
raw(O/'core_before_air.f32',O/'core_unmatched.f32','highshelf=f=12500:t=s:w=1:g=0.4')
core_ref=measure(B/'core_mix.f32');cur=measure(O/'core_unmatched.f32')
core_gain=float(core_ref['input_i'])-float(cur['input_i'])+.20
raw(O/'core_unmatched.f32',O/'core_mix.f32',f'volume={core_gain:.7f}dB')
core=np.array(arr(O/'core_mix.f32'));lead=core.mean(1)
print('CORE_READY',json.dumps({'new_gain_dB':core_gain,'ride_above_025dB_seconds':float(np.sum(ride>.25)*.01)}),flush=True)

# Preserve the V11 double's mid signal and pitch/timing; strengthen existing side information.
old_factor=10**(original['levels']['vocal_post_FX_gain_dB']/20)*original['levels']['FX_cap']
d=np.array(arr(B/'doubles.f32'))*old_factor
dm=d.mean(1);ds=(d[:,0]-d[:,1])*.5*10**(1.6/20)
doubles=np.column_stack([dm+ds,dm-ds]).astype('float32')
# Original V11 returns already include ducking. Extra gain happens primarily in gaps.
echo=np.array(arr(B/'echo.f32'))*old_factor*10**((.8*(1-activity[:,None]))/20)
shallow=np.array(arr(B/'shallow.f32'))*old_factor
deep=np.array(arr(B/'deep.f32'))*old_factor*10**((1.4*(1-activity[:,None]))/20)
fx=doubles+echo+shallow+deep
for name,x in [('doubles',doubles),('echo',echo),('shallow',shallow),('deep',deep),('fx_mix',fx)]:write(x,O/(name+'.f32'))
write(core+fx,O/'vocal.f32')
write(arr(C/'beat_clean.f32')+arr(O/'vocal.f32'),O/'premaster.f32')
vocal_measure=measure(O/'vocal.f32');fx_ratio=20*np.log10(rms(fx[active])/rms(lead[active]))
assert fx_ratio<-12,'Added production became substantially denser than intended'

target=float(original['master']['WAV_LUFS']);prem=measure(O/'premaster.f32')
gain=target-float(prem['input_i']);passes=[]
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
master=arr(O/'master.f32');vocal=arr(O/'vocal.f32')
assert len(master)==N and np.isfinite(master).all() and np.max(abs(master))<1
mono=float(10*np.log10(np.mean(master.mean(1)**2)/np.mean(master**2)));assert mono>-.8
mid=vocal.mean(1);side=(vocal[:,0]-vocal[:,1])/2
width={name:float(20*np.log10(rms(side[mask])/rms(mid[mask]))) for name,mask in [('active',active),('sustained',selected)]}
assert width['active']<-9 and width['sustained']<-9
for name,path in [('MUSIC_v12_POLISH',O/'master.f32'),('MUSIC_v12_VOCAL',O/'vocal.f32'),('MUSIC_v12_VOCAL_CORE',O/'core_mix.f32'),('MUSIC_v12_VOCAL_FX',O/'fx_mix.f32')]:
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(path),'-c:a','pcm_s24le',str(O/(name+'.wav'))],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(O/'MUSIC_v12_POLISH.wav'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v12_POLISH.mp3')],check=True)
mp=measure(O/'MUSIC_v12_POLISH.mp3',False);assert float(mp['input_tp'])<-.5

parts=[];comparison=[]
for label,path,start,end,level in [('V11_MIX',B/'master.f32',60,76,-16),('V12_MIX',O/'master.f32',60,76,-16),
                                 ('V11_VOCAL',B/'vocal.f32',100,110,-20),('V12_VOCAL',O/'vocal.f32',100,110,-20)]:
    x=np.array(arr(path)[start*SR:end*SR]);fade=np.linspace(0,1,384);x[:384]*=fade[:,None];x[-384:]*=fade[::-1,None]
    p=O/(label+'.f32');write(x,p);lm=measure(p);g=level-float(lm['input_i']);x*=10**(g/20);assert np.max(abs(x))<.99
    at=sum(len(a) for a in parts)/SR;comparison.append({'label':label,'start_s':at,'end_s':at+len(x)/SR,'target_LUFS':level,'gain_dB':g})
    parts.extend([x,np.zeros((SR//2,2),'float32')])
write(np.concatenate(parts[:-1]),O/'comparison.f32')
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(O/'comparison.f32'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v12_COMPARE.mp3')],check=True)
np.savez(O/'controls.npz',times=times,activity=act,voiced=voiced,drydb=drydb,ride=ride,edge=edge)
result={'basis':'Direct refinement of approved V11 core and separated V11 effects. Lead tuning, backing pitch/timing and phrase locations preserved; V9 accompaniment unchanged.',
 'lead':{'held_note_max_lift_dB':.9,'lift_target_band_dBFS':ride_target,'lift_above_025dB_s':float(np.sum(ride>.25)*.01),'lift_active_percentiles':{str(q):float(np.percentile(ride[active_frames],q)) for q in [50,90,95,99]},
         'existing_harmonic_residual_gain_change_dB':1.5,'edge_band':'6500Hz Q0.9, maximum -1.2dB','edge_detector_ratio_threshold_dB':edge_threshold,'edge_active_amount_percentiles':{str(q):float(np.percentile(edge[active_frames],q)) for q in [50,90,95,99]},
         'air_shelf':'12500Hz +0.4dB','core_LUFS_target_relative_V11':.2,'core_makeup_dB':core_gain},
 'space':{'existing_double_side_gain_dB':1.6,'double_mid_gain_dB':0,'echo_extra_gain_in_gaps_dB':.8,'deep_extra_gain_in_gaps_dB':1.4,'shallow_change_dB':0,'FX_active_RMS_relative_core_dB':fx_ratio,'vocal_side_mid_dB':width},
 'vocal_LUFS':float(vocal_measure['input_i']),
 'master':{'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),'MP3_LUFS':float(mp['input_i']),'MP3_dBTP':float(mp['input_tp']),'limiter':stats,'passes':passes,'mono_fold_energy_dB':mono,'duration_seconds':N/SR},
 'comparison':comparison,'limitations':'No subjective audition or claim of perfection. CORE still contains pre-existing printed effects. The new file refines the approved sound; signal metrics cannot certify aesthetic improvement.'}
(O/'validation.json').write_text(json.dumps(result,indent=2));print('COMPLETE',json.dumps(result),flush=True)
