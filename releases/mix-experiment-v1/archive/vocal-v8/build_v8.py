"""V8 reference-inspired vocal production. The user remains the sole vocal source."""
from pathlib import Path
exec(Path('/workspace/audio-final/master_v3.py').read_text().split('# Control isolated wet-vocal spikes')[0])
from scipy import ndimage
O=Path('/workspace/audio-v8');V=Path('/workspace/audio-reference')
rng=np.random.default_rng(20261016)

def rms(x):return float(np.sqrt(np.mean(np.asarray(x,dtype='float64')**2)))
def write(x,p):np.asarray(x,dtype='float32').tofile(p)
def filt(x,lo,hi,order=2):return signal.sosfilt(signal.butter(order,[lo,hi],fs=sr,btype='bandpass',output='sos'),x,axis=0).astype('float32')
def shift(x,t):
 k=round(t*sr);out=np.zeros_like(x)
 if k<len(x):out[k:]=x[:-k] if k else x
 return out

def envelope(w,attack=.015,release=.18,dt=.04):
 out=np.zeros_like(w);v=0.
 for i,q in enumerate(w):
  a=np.exp(-dt/(attack if q>v else release));v=a*v+(1-a)*q;out[i]=v
 return out

dryr=np.load(P/'dry_rms.npy');rt=np.arange(len(dryr))*.04+.02;db=20*np.log10(np.maximum(dryr,1e-12))
raw_activity=np.clip((db+52)/16,0,1)
held=ndimage.maximum_filter1d(raw_activity,size=3,origin=1,mode='nearest')
act_frames=envelope(held)
activity=np.interp(np.arange(N)/sr,rt,act_frames).astype('float32')
active=np.interp(np.arange(N)/sr,rt,dryr)>10**(-38/20)
# No further main-vocal compression: measured V7 strong syllables are already very level.
runraw(V/'vocal_final.f32',O/'core_unmatched.f32','highshelf=f=10000:t=s:w=1:g=0.8')
ref=measure(V/'vocal_final.f32');cur=measure(O/'core_unmatched.f32')
core_gain=float(ref['input_i'])-float(cur['input_i'])
runraw(O/'core_unmatched.f32',O/'core.f32',f'volume={core_gain:.7f}dB')
core=np.asarray(array(O/'core.f32')).copy();lead=core.mean(1);lead_rms=rms(lead[active])
# The original wet recording is baked. Soft activity control limits repeated recycling of its tail.
send=lead*activity
send=filt(send,280,6500)
write(send,O/'send_mono.f32')
print('CORE',{'LUFS':float(ref['input_i']),'active_mid_rms':lead_rms},flush=True)

# Detuned backing layers; intentionally different from an accidental raw/tuned double.
processes=[]
for name,cents in [('left',-7),('right',9)]:
 path=O/('double_'+name+'.f32')
 cmd=['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','1','-i',str(O/'send_mono.f32'),'-af',f'rubberband=pitch={2**(cents/1200):.10f}:tempo=1:formant=preserved:transients=smooth:detector=soft:pitchq=quality','-f','f32le',str(path)]
 processes.append((name,path,subprocess.Popen(cmd)))
doubles=np.zeros((N,2),dtype='float32');pitch_lengths={}
for c,(name,path,proc) in enumerate(processes):
 assert proc.wait()==0
 z=np.fromfile(path,dtype='float32');pitch_lengths[name]=len(z)
 z=np.pad(z[:N],(0,max(0,N-len(z))))
 z=shift(z,[.027,.043][c]);z=filt(z,300,6000)
 z*=lead_rms*10**(-13.5/20)/max(rms(z[active]),1e-12)
 doubles[:,c]=z
# No separate untreated lead is added; both backing voices derive from the tuned V7.
write(doubles,O/'doubles.f32');print('DOUBLES',pitch_lengths,flush=True)

# Eight sparse end-of-phrase accents, based on dry activity gaps rather than inferred words.
ends=[61.56,69.16,100.08,115.68,139.32,163.92,171.08,179.72]
throw=np.zeros(N,dtype='float32')
for end in ends:
 a=max(0,round((end-.38)*sr));b=min(N,round((end+.04)*sr))
 u=np.linspace(0,1,b-a);throw[a:b]=np.maximum(throw[a:b],np.sin(np.pi*u)**2)
delay_source=filt(send,330,4500)*(1+1.15*throw)
delay=np.zeros((N,2),dtype='float32')
# 135 BPM: 2,3,5,7,9 eighth-note subdivisions; repetitions become darker.
taps=[(2,1.,.12),(3,.12,1.),(5,.22,.035),(7,.035,.22),(9,.045,.02)]
for step,gl,gr in taps:
 src=delay_source if step<=3 else filt(delay_source,400,3000)
 z=shift(src,step*60/135/2);delay[:,0]+=z*gl;delay[:,1]+=z*gr
unducked_delay_rms=rms(delay[active]);delay_scale=lead_rms*10**(-18/20)/max(unducked_delay_rms,1e-12)
delay*=delay_scale
# Vocal-sidechain ducking: up to 7 dB during singing, smoothly restored in gaps.
delay*=10**((-7*activity[:,None])/20)
write(delay,O/'delay.f32')

# Smooth, diffuse late-tail IR. No discrete early room taps or short Haas widening.
L=round(sr*1.7);t=np.arange(L)/sr;common=rng.standard_normal(L);irs=[]
for c in range(2):
 noise=.25*common+np.sqrt(1-.25**2)*rng.standard_normal(L)
 lo=filt(noise,450,1800)*np.exp(-6.9078*t/1.35)
 hi=filt(noise,1800,6500)*np.exp(-6.9078*t/.95)
 h=(lo+.65*hi)*(1-np.exp(-t/.025))
 h=np.r_[np.zeros(round(.055*sr)),h];h/=np.sqrt(np.sum(h*h));irs.append(h.astype('float32'))
plate=np.column_stack([signal.oaconvolve(send,h)[:N] for h in irs]).astype('float32')
plate_scale=lead_rms*10**(-21.5/20)/max(rms(plate[active]),1e-12);plate*=plate_scale
plate*=10**((-4.5*activity[:,None])/20)
write(plate,O/'plate.f32')
fx=doubles+delay+plate
# Cap total added-effect strength rather than forcing a commercial-reference width number.
fx_ratio_db=20*np.log10(rms(fx[active])/lead_rms)
fx_gain=min(1.,10**((-12-fx_ratio_db)/20));fx*=fx_gain
# Preserve core level to within a small intended forward move after accounting for added returns.
write(core+fx,O/'vocal_unmatched.f32')
m=measure(O/'vocal_unmatched.f32');v_gain=float(ref['input_i'])+.45-float(m['input_i'])
vg=10**(v_gain/20);core*=vg;fx*=vg
write(core,O/'core_mix_level.f32');write(fx,O/'fx_mix_level.f32');write(core+fx,O/'vocal_mix_level.f32')
print('VOCAL',{'combined_gain_dB':v_gain,'effect_active_RMS_before_final_cap_dB':fx_ratio_db,'effect_cap_gain':fx_gain},flush=True)

# Preserve the user's V7 accompaniment exactly before mastering.
beat=array(V/'beat_final.f32');vocal=array(O/'vocal_mix_level.f32')
write(beat+vocal,O/'premaster.f32')
pre=measure(O/'premaster.f32');target=-11.;gain=target-float(pre['input_i']);history=[]
for attempt in range(5):
 runraw(O/'premaster.f32',O/'master.f32',f'volume={gain:.7f}dB,aresample=192000,alimiter=limit={10**(-1.3/20):.9f}:attack=5:release=80:level=0:latency=1,aresample=48000')
 m=measure(O/'master.f32');history.append({'gain_dB':gain,'LUFS':float(m['input_i']),'dBTP':float(m['input_tp'])});d=target-float(m['input_i'])
 if abs(d)<.05:break
 gain+=d
stats=gain_stats(O/'premaster.f32',O/'master.f32',10**(gain/20))
assert abs(float(m['input_i'])-target)<.12
assert float(m['input_tp'])<-1.1
assert stats['gain_reduction_dB_percentiles']['95']<4.0
assert stats['active_percent_over_3dB']<6
x=array(O/'master.f32');assert len(x)==N and np.isfinite(x).all() and abs(x).max()<1
mono_loss=float(10*np.log10(np.mean(x.mean(1)**2)/np.mean(x**2)));assert mono_loss>-.8
v=array(O/'vocal_mix_level.f32');vmid=v.mean(1);vside=(v[:,0]-v[:,1])/2
side_mid=float(20*np.log10(rms(vside[active])/rms(vmid[active])))
outputs={}
for name,path in [('MUSIC_v8_1CALL',O/'master.f32'),('MUSIC_v8_VOCAL',O/'vocal_mix_level.f32'),('MUSIC_v8_VOCAL_CORE',O/'core_mix_level.f32'),('MUSIC_v8_VOCAL_FX',O/'fx_mix_level.f32')]:
 subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(path),'-c:a','pcm_s24le',str(O/(name+'.wav'))],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(O/'MUSIC_v8_1CALL.wav'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v8_1CALL.mp3')],check=True)
mp=measure(O/'MUSIC_v8_1CALL.mp3',False);assert float(mp['input_tp'])<-.5
# Compare passages that contain both lead singing and phrase-end spaces.
clips=[];comparison=[]
for label,path in [('V7',V/'master.f32'),('V8',O/'master.f32')]:
 y=array(path);parts=[]
 for a,b in [(60,72),(98,106)]:
  c=np.array(y[a*sr:b*sr]);fade=np.linspace(0,1,384);c[:384]*=fade[:,None];c[-384:]*=fade[::-1,None];parts.append(c)
  if b==72:parts.append(np.zeros((sr//4,2),dtype='float32'))
 c=np.concatenate(parts);tmp=O/(label+'_compare.f32');write(c,tmp);cm=measure(tmp);g=-16-float(cm['input_i']);c*=10**(g/20)
 start=sum(len(a) for a in clips)/sr;comparison.append({'label':label,'start_seconds':start,'duration_seconds':len(c)/sr,'gain_dB':g,'target_LUFS':-16})
 clips.extend([c,np.zeros((sr//2,2),'float32')])
write(np.concatenate(clips[:-1]),O/'compare.f32')
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(O/'compare.f32'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v8_COMPARE.mp3')],check=True)
validation={'basis':'V7 original user vocal and accompaniment; commercial reference used only for analysis, never added to audio','reference_evidence':'UVR-MDX-NET estimated vocal excerpts show substantially greater side information, broadly similar 1.2–5kHz balance, and no justification for more heavy lead compression. Separation is imperfect.','lead':{'air_shelf':'10kHz +0.8dB; core loudness matched before added effects','new_compression':'none','main_vocal_target_relative_V7_LU':.45,'combined_gain_after_effects_dB':v_gain},'doubles':{'cents':[-7,9],'delay_ms':[27,43],'formant':'preserved','bandpass_Hz':[300,6000],'each_channel_active_RMS_relative_lead_dB':-13.5,'rendered_sample_counts':pitch_lengths},'delay':{'tempo_BPM':135,'half_time_BPM':67.5,'initial_taps_ms':[444.444,666.667],'later_taps_ms':[1111.111,1555.556,2000.],'main_bandpass_Hz':[330,4500],'initial_return_active_RMS_dB':-18,'duck_max_dB':7,'throw_candidates_s':ends},'diffuse_tail':{'predelay_ms':55,'nominal_low_T60_s':1.35,'nominal_high_T60_s':.95,'low_cut_Hz':450,'initial_return_active_RMS_dB':-21.5,'duck_max_dB':4.5},'effects':{'before_cap_active_RMS_relative_lead_dB':fx_ratio_db,'cap_gain':fx_gain,'new_total_vocal_active_side_mid_dB':side_mid},'master':{'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),'MP3_LUFS':float(mp['input_i']),'MP3_dBTP':float(mp['input_tp']),'passes':history,'limiter':stats,'mono_fold_energy_dB':mono_loss,'duration_seconds':N/sr},'comparison':comparison,'limitations':'No subjective audition. This is an original mixing interpretation, not identification or reconstruction of the artist original plugin settings or vocal identity. Artificial doubles and new returns can affect mono tone; separate core/FX provided for revision.'}
(O/'validation.json').write_text(json.dumps(validation,indent=2));print('COMPLETE',json.dumps(validation),flush=True)
