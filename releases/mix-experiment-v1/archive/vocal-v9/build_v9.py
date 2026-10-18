"""V9 whole-mix cleanup: bounded tone/masking correction and reduced added layering."""
from pathlib import Path
exec(Path('/workspace/audio-final/master_v3.py').read_text().split('# Control isolated wet-vocal spikes')[0])
from scipy import ndimage
O=Path('/workspace/audio-clean');V=Path('/workspace/audio-reference');E=Path('/workspace/audio-v8')
H=480;K=(N+H-1)//H;times=(np.arange(K)+.5)*H/sr

def write(x,p):np.asarray(x,dtype='float32').tofile(p)
def interp(v):return np.interp(np.arange(N)/sr,times,v).astype('float32')
def rms(x):return float(np.sqrt(np.mean(np.asarray(x,dtype='float64')**2)))
def smooth(w,attack=.035,release=.18):
 out=np.empty_like(w);v=float(w[0])
 for i,q in enumerate(w):
  a=np.exp(-.01/(attack if q>v else release));v=a*v+(1-a)*q;out[i]=v
 return out

def power(x,lo,hi):
 z=signal.sosfilt(signal.butter(2,[lo,hi],fs=sr,btype='bandpass',output='sos'),x)
 z=np.pad(z,(0,K*H-len(z)));p=np.mean(z.reshape(K,H)**2,axis=1)
 return ndimage.gaussian_filter1d(p,3)

def peak(f,q,db):
 A=10**(db/40);w=2*np.pi*f/sr;alpha=np.sin(w)/(2*q)
 b=np.array([1+alpha*A,-2*np.cos(w),1-alpha*A]);a=np.array([1+alpha/A,-2*np.cos(w),1-alpha/A])
 return np.r_[b/a[0],a/a[0]].reshape(1,6)

dryr=np.load(P/'dry_rms.npy');drydb=np.interp(times,np.arange(len(dryr))*.04+.02,20*np.log10(np.maximum(dryr,1e-12)))
act=np.clip((drydb+52)/16,0,1);act=ndimage.maximum_filter1d(act,size=9,origin=4,mode='nearest');act=smooth(act,.01,.18)
activity=interp(act);active_frames=(drydb>-38)&(times>6)&(times<192);active=interp(active_frames.astype(float))>.9
old_v=array(V/'vocal_final.f32');old_b=array(V/'beat_final.f32')
# Keep the user's V7 tonal base, with no additional V8 air shelf.
runraw(V/'vocal_final.f32',O/'vocal_static.f32','highpass=f=85:p=2,equalizer=f=250:t=q:w=0.9:g=-0.8')
v=np.asarray(array(O/'vocal_static.f32')).copy();mid=old_v.mean(1)
ratio=10*np.log10((power(mid,125,350)+1e-15)/(power(mid,600,3000)+1e-15))
th=float(np.percentile(ratio[active_frames],40));amount=smooth(np.clip((ratio-th)/6,0,1),.04,.18)*act
cut=signal.sosfilt(peak(250,.9,-.8),v,axis=0).astype('float32');v+=(cut-v)*interp(amount)[:,None]
write(v,O/'vocal_clean_core_unmatched.f32');del cut,v
# Voice-relative accompaniment control: most relief where the band competes with a weak phrase.
bmid=old_b.mean(1);bside=(old_b[:,0]-old_b[:,1])/2
vr=power(mid,600,2000);br=power(bmid,600,2000);competition=10*np.log10((br+1e-15)/(vr+1e-15))
dose=(.25+.75*np.clip((competition+5)/7,0,1))*act;dose=smooth(dose,.035,.18)
cut=signal.sosfilt(peak(800,.8,-2.5),bmid).astype('float32');bm=bmid+(cut-bmid)*interp(dose)
# Keep stereo balance and bass; no extra brightening or widening.
write(np.column_stack([bm+bside,bm-bside]),O/'beat_clean_unmatched.f32');del cut,bm,bside,bmid

# Lower the persistent artificial doubles most; preserve quieter phrase-end space.
doubles=array(E/'doubles.f32');delay=array(E/'delay.f32');plate=array(E/'plate.f32')
fx=(np.asarray(doubles)*10**(-6/20)+np.asarray(delay)*10**(-2/20)+np.asarray(plate)*10**(-3/20)).astype('float32')
fx=signal.sosfilt(signal.butter(2,500,fs=sr,btype='highpass',output='sos'),fx,axis=0).astype('float32')
# V8 returns above were saved before the shared final vocal compensation; normalize the whole rebuilt bus below.
write(fx,O/'fx_light.f32')
ref_v=measure(V/'vocal_final.f32');ref_b=measure(V/'beat_final.f32')
# Control bus: fewer effects + gentler master, but no new tonal/sidechain cleanup.
write(old_v+fx,O/'control_vocal_unmatched.f32')
# Main bus: same reduced effects, cleaned vocal and competition-aware accompaniment.
write(array(O/'vocal_clean_core_unmatched.f32')+fx,O/'clean_vocal_unmatched.f32')
levels={}
for name in ['control','clean']:
 m=measure(O/(name+'_vocal_unmatched.f32'));g=float(ref_v['input_i'])+.15-float(m['input_i'])
 runraw(O/(name+'_vocal_unmatched.f32'),O/(name+'_vocal.f32'),f'volume={g:.7f}dB');levels[name+'_vocal_gain_dB']=g
q=measure(O/'beat_clean_unmatched.f32');bg=float(ref_b['input_i'])-float(q['input_i']);levels['beat_clean_compensation_dB']=bg
runraw(O/'beat_clean_unmatched.f32',O/'beat_clean.f32',f'volume={bg:.7f}dB')
outputs={}
for name,stem,bpath in [('MUSIC_v9_CLEAN',O/'clean_vocal.f32',O/'beat_clean.f32'),('MUSIC_v9_LIGHT_CONTROL',O/'control_vocal.f32',V/'beat_final.f32')]:
 write(array(stem)+array(bpath),O/(name+'_premaster.f32'))
 pre=measure(O/(name+'_premaster.f32'));gain=-12.1-float(pre['input_i']);passes=[];dest=O/(name+'.f32')
 for attempt in range(5):
  runraw(O/(name+'_premaster.f32'),dest,f'volume={gain:.7f}dB,aresample=192000,alimiter=limit={10**(-1.4/20):.9f}:attack=5:release=80:level=0:latency=1,aresample=48000')
  m=measure(dest);passes.append({'gain_dB':gain,'LUFS':float(m['input_i']),'dBTP':float(m['input_tp'])});d=-12.1-float(m['input_i'])
  if abs(d)<.05:break
  gain+=d
 stats=gain_stats(O/(name+'_premaster.f32'),dest,10**(gain/20))
 assert abs(float(m['input_i'])+12.1)<.12 and float(m['input_tp'])<-1.1
 assert stats['gain_reduction_dB_percentiles']['95']<2.5 and stats['active_percent_over_3dB']<2
 x=array(dest);assert len(x)==N and np.isfinite(x).all() and abs(x).max()<1
 mono=float(10*np.log10(np.mean(x.mean(1)**2)/np.mean(x**2)));assert mono>-.8
 wav=O/(name+'.wav');mp3=O/(name+'.mp3')
 subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(dest),'-c:a','pcm_s24le',str(wav)],check=True)
 subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-c:a','libmp3lame','-b:a','320k',str(mp3)],check=True)
 mp=measure(mp3,False);assert float(mp['input_tp'])<-.5
 outputs[name]={'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),'MP3_LUFS':float(mp['input_i']),'MP3_dBTP':float(mp['input_tp']),'mono_fold_energy_dB':mono,'limiter':stats,'passes':passes}
 print(name,json.dumps(outputs[name]),flush=True)
for name,src in [('MUSIC_v9_VOCAL',O/'clean_vocal.f32'),('MUSIC_v9_BEAT',O/'beat_clean.f32')]:
 subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(src),'-c:a','pcm_s24le',str(O/(name+'.wav'))],check=True)
# Stepwise matched comparison, same two passages as V8 comparison.
clips=[];comp=[]
for label,path in [('V8',E/'master.f32'),('LIGHT_CONTROL',O/'MUSIC_v9_LIGHT_CONTROL.f32'),('V9_CLEAN',O/'MUSIC_v9_CLEAN.f32')]:
 y=array(path);parts=[]
 for a,b in [(60,72),(98,106)]:
  c=np.array(y[a*sr:b*sr]);fade=np.linspace(0,1,384);c[:384]*=fade[:,None];c[-384:]*=fade[::-1,None];parts.append(c)
  if b==72:parts.append(np.zeros((sr//4,2),'float32'))
 c=np.concatenate(parts);tmp=O/(label+'_compare.f32');write(c,tmp);m=measure(tmp);g=-16-float(m['input_i']);c*=10**(g/20)
 start=sum(len(q) for q in clips)/sr;comp.append({'label':label,'start_s':start,'end_s':start+len(c)/sr,'target_LUFS':-16,'gain_dB':g})
 clips.extend([c,np.zeros((sr//2,2),'float32')])
write(np.concatenate(clips[:-1]),O/'comparison.f32')
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(O/'comparison.f32'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v9_COMPARE.mp3')],check=True)
result={'purpose':'Whole-mix cleanup proposal responding to perceived muddiness/dirty sound; not a confirmed diagnosis','reference':'V7 tonal base and V8 effects separated; original tuning retained','vocal':'85Hz 2-pole HP; 250Hz Q.9 -0.8dB static plus at most -0.8dB dynamic, 40ms attack /180ms release; no new air boost','vocal_detector':{'ratio_bands_Hz':[[125,350],[600,3000]],'threshold_dB':th,'active_reduction_amount_percentiles':{str(q):float(np.percentile(amount[active_frames],q)) for q in [10,50,90,99]}},'beat':'Mid-only 800Hz Q.8 maximum -2.5dB, competition-aware during voice; original bass and side retained before global level match','beat_detector':{'ratio_band_Hz':[600,2000],'active_dose_percentiles':{str(q):float(np.percentile(dose[active_frames],q)) for q in [10,50,90,99]}},'new_effects_relative_V8_pre_bus':{'doubles_dB':-6,'delay_dB':-2,'plate_dB':-3,'all_new_FX_highpass_Hz':500},'levels':levels,'duration_seconds':N/sr,'outputs':outputs,'comparison':comp,'control_limitations':'LIGHT_CONTROL jointly reduces effects, removes the V8 +0.8dB air shelf, and uses a gentler master; it does not isolate each of those changes separately. CLEAN adds vocal/body and beat/masking correction on that same basis.','limitations':'No subjective audition. Cannot infer that low-mid balance, reverb, or limiter is the sole source of perceived dirt; printed recording and original processing remain.'}
(O/'validation.json').write_text(json.dumps(result,indent=2));print('COMPLETE',flush=True)
