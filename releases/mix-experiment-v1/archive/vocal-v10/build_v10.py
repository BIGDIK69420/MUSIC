"""V10: a fresh vocal path from the original dry recording, not the printed wet chain."""
from pathlib import Path
exec(Path('/workspace/audio-final/master_v3.py').read_text().split('# Control isolated wet-vocal spikes')[0])
import argparse
from scipy import ndimage
ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);args=ap.parse_args()
O=Path('/workspace/audio-rebuild');C=Path('/workspace/audio-clean');src=Path(args.source)
x=np.fromfile(src,dtype='float32');assert len(x)==N and np.isfinite(x).all(),(src,len(x),N)
np.column_stack([x,x]).astype('float32').tofile(O/'source_stereo.f32')

def write(x,p):np.asarray(x,dtype='float32').tofile(p)
def rms(x):return float(np.sqrt(np.mean(np.asarray(x,dtype='float64')**2)))
def smooth(w,at,rel,dt):
 out=np.empty_like(w);v=float(w[0])
 for i,q in enumerate(w):
  a=np.exp(-dt/(at if q>v else rel));v=a*v+(1-a)*q;out[i]=v
 return out

def bp(x,lo,hi):return signal.sosfilt(signal.butter(2,[lo,hi],fs=sr,btype='bandpass',output='sos'),x).astype('float32')

def shift(x,sec):
 k=round(sec*sr);out=np.zeros_like(x);out[k:]=x[:-k];return out

# Clean the specific narrow 100Hz residue gently; no wholesale spectral flattening.
runraw(O/'source_stereo.f32',O/'filtered.f32','highpass=f=75:p=2,equalizer=f=100:t=q:w=20:g=-4')
x=np.array(array(O/'filtered.f32'));m=x.mean(1)
H=960;K=(N+H-1)//H;t=(np.arange(K)+.5)*H/sr
p=bp(m,150,4500);p=np.pad(p,(0,K*H-N));en=np.mean(p.reshape(K,H)**2,axis=1)
db=10*np.log10(np.maximum(en,1e-15));dryr=np.load(P/'dry_rms.npy');drydb=np.interp(t,np.arange(len(dryr))*.04+.02,20*np.log10(np.maximum(dryr,1e-12)))
weights=np.clip((drydb+48)/12,0,1)
den=ndimage.gaussian_filter1d(weights,12.5)
num=ndimage.gaussian_filter1d(db*weights,12.5)
valid=den>=.04
assert valid.any(), 'No reliable active frames for level riding'
# Carry reliable phrase levels through gaps instead of mistaking silence for 0 dBFS.
# Between-phrase noise reduction is handled separately by the held activity gain.
local=np.interp(t,t[valid],num[valid]/den[valid])
ride=np.clip(((-24)-local)*.72,-4,6)
ride=ndimage.gaussian_filter1d(ride,8)
# Bound gain speed; no fast gain tracking of individual pitch cycles or all breaths.
for i in range(1,K):ride[i]=np.clip(ride[i],ride[i-1]-.10,ride[i-1]+.10)
for i in range(K-2,-1,-1):ride[i]=np.clip(ride[i],ride[i+1]-.10,ride[i+1]+.10)
gain=np.interp(np.arange(N)/sr,t,ride).astype('float32')
x*=10**(gain[:,None]/20);write(x,O/'ridden.f32')
# Start afresh; this is not stacked on the prior RX/Auto-Level/MC77/de-ess/spatial chain.
eq='equalizer=f=260:t=q:w=0.9:g=-1.0,equalizer=f=520:t=q:w=1.1:g=-1.5,equalizer=f=1700:t=q:w=0.8:g=1.3,equalizer=f=3300:t=q:w=0.9:g=3.2,highshelf=f=6500:t=s:w=1:g=3.0'
runraw(O/'ridden.f32',O/'eq.f32',eq)
runraw(O/'eq.f32',O/'compressed.f32','acompressor=threshold=0.05:ratio=2.5:attack=15:release=110:makeup=1:knee=2.828:detection=rms:link=maximum')
compressor_stats=gain_stats(O/'eq.f32',O/'compressed.f32')
# One bounded high-band de-esser, signal linked. It cannot remove pre-existing source distortion.
y=np.array(array(O/'compressed.f32'));mono=y.mean(1)
def fp(z):
 z=np.pad(z,(0,K*H-N));return ndimage.gaussian_filter1d(np.mean(z.reshape(K,H)**2,axis=1),1.5)
hi=fp(bp(mono,5000,11000));speech=fp(bp(mono,1200,4500));ratio=10*np.log10((hi+1e-15)/(speech+1e-15))
active_frames=drydb>-38
threshold=max(-8.,float(np.percentile(ratio[active_frames],80)))
amount=smooth(np.clip((ratio-threshold)/7,0,1),.008,.075,.02)
# Blend toward a fixed high-shelf cut for smooth, limited attenuation.
runraw(O/'compressed.f32',O/'deess_cut.f32','highshelf=f=5500:t=s:w=1:g=-3')
cut=array(O/'deess_cut.f32');a=np.interp(np.arange(N)/sr,t,amount).astype('float32');y+=(cut-y)*a[:,None]
# Soft, held between-phrase attenuation; never zero the input.
act=np.clip((drydb+54)/12,0,1);act=ndimage.maximum_filter1d(act,size=7,origin=3,mode='nearest');act=smooth(act,.01,.20,.02)
activity=np.interp(np.arange(N)/sr,t,act).astype('float32');y*=.35+.65*activity[:,None]
write(y,O/'core_before_level.f32')
ref=measure(C/'clean_vocal.f32');cur=measure(O/'core_before_level.f32');initial_gain=float(ref['input_i'])-float(cur['input_i'])
runraw(O/'core_before_level.f32',O/'core_levelled.f32',f'volume={initial_gain:.7f}dB')
# Catch isolated peaks only after makeup, with latency compensation and no auto makeup.
runraw(O/'core_levelled.f32',O/'core_peak_safe.f32',f'aresample=192000,alimiter=limit={10**(-5.5/20):.9f}:attack=1:release=20:level=0:latency=1,aresample=48000')
peak_stats=gain_stats(O/'core_levelled.f32',O/'core_peak_safe.f32')
assert peak_stats['gain_reduction_dB_percentiles']['95']<1.5
assert peak_stats['active_percent_over_3dB']<1.5
core=np.array(array(O/'core_peak_safe.f32'));lead=core.mean(1);active=np.interp(np.arange(N)/sr,t,active_frames.astype(float))>.9
lr=rms(lead[active]);send=bp(lead,550,5500)*activity
# Very low, ducked new space. No old wet file or sustained artificial double enters the result.
delay=np.column_stack([shift(send,60/135),shift(send,90/135)]).astype('float32')
delay*=lr*10**(-27/20)/max(rms(delay[active]),1e-12);delay*=10**((-7*activity[:,None])/20)
rng=np.random.default_rng(20261017);L=round(sr*1.2);tt=np.arange(L)/sr;irs=[]
for channel in range(2):
 n=rng.standard_normal(L);h=bp(n,650,5500)*np.exp(-6.9078*tt/.85)*(1-np.exp(-tt/.025));h=np.r_[np.zeros(round(.055*sr)),h];h/=np.sqrt(np.sum(h*h));irs.append(h.astype('float32'))
rev=np.column_stack([signal.oaconvolve(send,h)[:N] for h in irs]).astype('float32')
rev*=lr*10**(-26/20)/max(rms(rev[active]),1e-12);rev*=10**((-5*activity[:,None])/20)
fx=delay+rev;write(core+fx,O/'vocal_unmatched.f32')
q=measure(O/'vocal_unmatched.f32');vg=float(ref['input_i'])-float(q['input_i']);vfac=10**(vg/20)
write(core*vfac,O/'core.f32');write(fx*vfac,O/'fx.f32');write((core+fx)*vfac,O/'vocal.f32')
write(array(C/'beat_clean.f32')+array(O/'vocal.f32'),O/'premaster.f32')
p=measure(O/'premaster.f32');gain=-12.1-float(p['input_i']);passes=[]
for i in range(5):
 runraw(O/'premaster.f32',O/'master.f32',f'volume={gain:.7f}dB,aresample=192000,alimiter=limit={10**(-1.4/20):.9f}:attack=5:release=80:level=0:latency=1,aresample=48000')
 m=measure(O/'master.f32');passes.append({'gain_dB':gain,'LUFS':float(m['input_i']),'dBTP':float(m['input_tp'])});delta=-12.1-float(m['input_i'])
 if abs(delta)<.05:break
 gain+=delta
master_stats=gain_stats(O/'premaster.f32',O/'master.f32',10**(gain/20))
assert abs(float(m['input_i'])+12.1)<.12 and float(m['input_tp'])<-1.1
assert master_stats['gain_reduction_dB_percentiles']['95']<3 and master_stats['active_percent_over_3dB']<3
z=array(O/'master.f32');assert np.isfinite(z).all() and np.max(abs(z))<1 and len(z)==N
mono_loss=float(10*np.log10(np.mean(z.mean(1)**2)/np.mean(z**2)))
assert mono_loss>-.8
for name,path in [('MUSIC_v10_REBUILD',O/'master.f32'),('MUSIC_v10_VOCAL',O/'vocal.f32'),('MUSIC_v10_VOCAL_CORE',O/'core.f32')]:
 subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(path),'-c:a','pcm_s24le',str(O/(name+'.wav'))],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(O/'MUSIC_v10_REBUILD.wav'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v10_REBUILD.mp3')],check=True)
mp=measure(O/'MUSIC_v10_REBUILD.mp3',False);assert float(mp['input_tp'])<-.5
# Full-mix A/B followed by solo-vocal A/B makes the changed source easier to isolate.
clips=[];comp=[]
for label,path,target in [('V9_MIX',C/'MUSIC_v9_CLEAN.f32',-16),('V10_MIX',O/'master.f32',-16),('V9_VOCAL',C/'clean_vocal.f32',-20),('V10_VOCAL',O/'vocal.f32',-20)]:
 start,end=(60,76) if 'MIX' in label else (100,110)
 clip=np.array(array(path)[start*sr:end*sr]);fade=np.linspace(0,1,384);clip[:384]*=fade[:,None];clip[-384:]*=fade[::-1,None]
 temp=O/(label+'_clip.f32');write(clip,temp);lm=measure(temp);g=target-float(lm['input_i']);clip*=10**(g/20)
 assert abs(clip).max()<.99
 at=sum(len(q) for q in clips)/sr;comp.append({'label':label,'start_s':at,'end_s':at+len(clip)/sr,'target_LUFS':target,'gain_dB':g})
 clips.extend([clip,np.zeros((sr//2,2),'float32')])
write(np.concatenate(clips[:-1]),O/'comparison.f32')
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(O/'comparison.f32'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v10_COMPARE.mp3')],check=True)
result={'source':str(src),'approach':'Independent rebuilding from the dry recording, conservative restoration and verified pitch guidance upstream. Printed wet vocal is never mixed into this audio.','filters':{'HP_Hz':75,'hum_notch':'100Hz Q20 -4dB','tone':eq},'riding':{'reference_band_Hz':[150,4500],'target_dBFS':-24,'range_dB':[-4,6],'maximum_slew_dB_per_s':5,'active_gain_percentiles_dB':{str(q):float(np.percentile(ride[active_frames],q)) for q in [10,50,90]}},'compressor':{'ratio':2.5,'threshold_dBFS':20*np.log10(.05),'attack_ms':15,'release_ms':110,'statistics':compressor_stats},'deesser':{'high_band_Hz':[5000,11000],'threshold_ratio_dB':threshold,'maximum_shelf_cut_dB':3},'level':{'initial_makeup_dB':initial_gain,'after_peak_and_fx_compensation_dB':vg,'vocal_LUFS_target':float(ref['input_i'])},'isolated_peak_control':peak_stats,'space':{'delay_ms':[444.444,666.667],'delay_relative_active_RMS_dB':-27,'delay_duck_dB':7,'diffuse_T60_s':.85,'predelay_ms':55,'diffuse_return_active_RMS_dB':-26,'diffuse_duck_dB':5},'master':{'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),'MP3_LUFS':float(mp['input_i']),'MP3_dBTP':float(mp['input_tp']),'limiter':master_stats,'passes':passes,'mono_fold_energy_dB':mono_loss,'duration_seconds':N/sr},'comparison':comp,'limitations':'No subjective audition. Separation/repair is imperfect and pitch guidance is confidence-limited, not exact reproduction of the original Auto-Tune settings. Cannot guarantee removal of perceived phone-like quality.'}
(O/'validation.json').write_text(json.dumps(result,indent=2));print('COMPLETE',json.dumps(result),flush=True)
