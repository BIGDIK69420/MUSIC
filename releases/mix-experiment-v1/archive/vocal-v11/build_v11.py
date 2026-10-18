"""V11: phrase-shaped R&B vocal production from the original tuned V7 lead."""
from pathlib import Path
import json,re,subprocess
import numpy as np
from scipy import signal,ndimage

O=Path('/workspace/audio-v11');O.mkdir(exist_ok=True)
P=Path('/workspace/audio-analysis');V=Path('/workspace/audio-reference');C=Path('/workspace/audio-clean')
SR=48000;N=(V/'vocal_final.f32').stat().st_size//8;H=480;K=(N+H-1)//H
times=(np.arange(K)+.5)*H/SR
def arr(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def write(x,p):np.asarray(x,dtype='float32').tofile(p)
def rms(x):return float(np.sqrt(np.mean(np.asarray(x,dtype='float64')**2)))
def interp(v):return np.interp(np.arange(N)/SR,times,v).astype('float32')
def raw(src,dst,flt):
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(src),'-af',flt,'-f','f32le',str(dst)],check=True)
    assert dst.stat().st_size==N*8,(dst,dst.stat().st_size)
def measure(p,raw_input=True):
    cmd=['ffmpeg','-hide_banner','-nostats']
    if raw_input:cmd+=['-f','f32le','-ar',str(SR),'-ac','2']
    result=subprocess.run(cmd+['-i',str(p),'-af','loudnorm=I=-12:TP=-1.3:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
    return json.loads(re.search(r'\{\s*"input_i".*?\}',result.stderr,re.S).group())
def smooth(v,attack=.025,release=.15):
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
def shift(x,seconds):
    k=round(seconds*SR);y=np.zeros_like(x)
    if 0<k<len(x):y[k:]=x[:-k]
    elif k==0:y[:]=x
    return y
def gain_stats(before,after,drive=1):
    x=arr(before);y=arr(after);n=min(len(x),len(y))//48*48
    x=np.asarray(x[:n]).reshape(-1,48,2)*drive;y=np.asarray(y[:n]).reshape(-1,48,2)
    e=np.sum(x*x,axis=(1,2));g=np.sum(x*y,axis=(1,2))/np.maximum(e,1e-16)
    gr=-20*np.log10(np.clip(g[e/96>1e-5],1e-6,1))
    return {'method':'Approximate 1 ms least-squares gain, active input > -50 dBFS; includes resampling differences.',
            'gain_reduction_dB_percentiles':{str(p):float(np.percentile(gr,p)) for p in [50,90,95,99,99.9,100]},
            'active_percent_over_3dB':float(100*np.mean(gr>3))}

dry_rms=np.load(P/'dry_rms.npy')
drydb=np.interp(times,np.arange(len(dry_rms))*.04+.02,20*np.log10(np.maximum(dry_rms,1e-12)))
act=np.clip((drydb+50)/14,0,1)
act=smooth(ndimage.maximum_filter1d(act,9,origin=4,mode='nearest'),.012,.17)
activity=interp(act);active_frames=(drydb>-38)&(times>6)&(times<192);active=interp(active_frames.astype(float))>.9

# The existing pitch is retained. No V10 reconstruction or new lead pitch shifter is used.
static_eq='highpass=f=80:p=2,equalizer=f=300:t=q:w=0.9:g=0.4,highshelf=f=10000:t=s:w=1:g=0.7'
raw(V/'vocal_final.f32',O/'tone_static.f32',static_eq)
x=np.array(arr(O/'tone_static.f32'));m=x.mean(1);dynamic=[]
for name,f,q,maxcut,band,shoulders,percentile in [
    ('occasional_mid_prominence',900,1.8,-.8,(700,1100),[(350,600),(1400,2300)],80),
    ('occasional_edge',4000,1.1,-1.,(3000,5000),[(1200,2500)],85)]:
    p=power(m,*band)/(band[1]-band[0])
    ref=sum(power(m,*b)/(b[1]-b[0]) for b in shoulders)/len(shoulders)
    ratio=10*np.log10((p+1e-18)/(ref+1e-18));threshold=float(np.percentile(ratio[active_frames],percentile))
    amount=smooth(np.clip((ratio-threshold)/6,0,1),.02,.12)*act
    cut=signal.sosfilt(peak(f,q,maxcut),x,axis=0).astype('float32');x+=(cut-x)*interp(amount)[:,None]
    dynamic.append({'name':name,'Hz':f,'Q':q,'maximum_cut_dB':maxcut,'threshold_ratio_dB':threshold,
                    'active_amount_percentiles':{str(p):float(np.percentile(amount[active_frames],p)) for p in [50,90,99]}})

# Existing pitch analysis is used only to choose sustained voiced spans for backing layers.
c=np.load('/workspace/audio-v10-pitch/comparison.npz')
vflag=(c['mixed']>65)&(c['mixed_periodicity']>.68)
vflag=np.interp(times,c['t'],vflag.astype(float))>.9;vflag&=drydb>-42
vflag=ndimage.binary_closing(vflag,structure=np.ones(4))
labels,count=ndimage.label(vflag);sizes=np.bincount(labels)
selected=vflag&(sizes[labels]>=35)
voiced=np.zeros(K);regions=[]
for label in np.unique(labels[selected]):
    ids=np.flatnonzero(labels==label);a,b=ids[0],ids[-1]+1;n=b-a
    u=np.arange(n)*.01;d=(n-1-np.arange(n))*.01
    # Onsets stay on the main voice; the backing opens over the held vowel.
    shape=np.sin(np.pi/2*np.clip((u-.06)/.12,0,1))**2*np.sin(np.pi/2*np.clip(d/.09,0,1))**2
    voiced[a:b]=shape;regions.append([float(times[a]),float(times[b-1]+.01)])
voiced=smooth(voiced,.015,.04)*act;vowel=interp(voiced)
assert np.sum(voiced>.5)>1000,'Too little selected singing for the intended backing design'

# Quiet harmonic color: 4x oversampling and only the nonlinear residual, not another loud duplicate.
lead=x.mean(1);body=bp(lead,220,2400)
drive=.6/max(rms(body[active]),1e-8);up=signal.resample_poly(body.astype('float64'),4,1)
sat=np.tanh(drive*up+.08)-np.tanh(.08)
sat=signal.resample_poly(sat,1,4)[:N].astype('float32');del up
linear=float(np.dot(body[active].astype('float64'),sat[active])/np.dot(body[active].astype('float64'),body[active]))
color=bp(sat-linear*body,250,5200)*vowel
color*=rms(lead[active])*10**(-32/20)/max(rms(color[active]),1e-10)
x+=color[:,None];write(color,O/'harmonic_color_mono.f32');write(x,O/'core_unmatched.f32')
ref=measure(V/'vocal_final.f32');cur=measure(O/'core_unmatched.f32')
core_gain=float(ref['input_i'])-float(cur['input_i'])
raw(O/'core_unmatched.f32',O/'core.f32',f'volume={core_gain:.7f}dB')
core=np.array(arr(O/'core.f32'));lead=core.mean(1);lr=rms(lead[active]);vowel_samples=vowel>.65
print('CORE_READY',json.dumps({'gain_dB':core_gain,'vowel_selected_s':float(np.sum(vowel>.5)/SR),'regions':len(regions)}),flush=True)

# Backing voices only on the selected vowels; their render does not alter the lead track.
send=bp(lead,420,6100)*vowel;write(send,O/'vowel_send_mono.f32')
processes=[]
for channel,cents in enumerate([-6,7]):
    path=O/f'backing_{channel}.f32'
    cmd=['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','1','-i',str(O/'vowel_send_mono.f32'),'-af',
         f'rubberband=pitch={2**(cents/1200):.10f}:tempo=1:formant=preserved:transients=smooth:detector=soft:pitchq=quality','-f','f32le',str(path)]
    processes.append((path,subprocess.Popen(cmd)))
doubles=np.zeros((N,2),dtype='float32');pitch_lengths=[]
for channel,(path,proc) in enumerate(processes):
    assert proc.wait()==0;z=np.fromfile(path,dtype='float32');pitch_lengths.append(len(z));assert abs(len(z)-N)<SR*.03
    z=np.pad(z[:N],(0,max(0,N-len(z))));z=shift(bp(z,420,6100),[.031,.049][channel])
    z*=rms(lead[vowel_samples])*10**(-11.5/20)/max(rms(z[vowel_samples]),1e-9)
    doubles[:,channel]=z
write(doubles,O/'doubles.f32')

# Sparse phrase-end sends. Alternate one echo rhythm per phrase rather than continual dual delays.
ends=[13.96,18.76,28.84,61.56,69.16,100.08,115.68,139.32,163.92,171.08,179.72]
throw=np.zeros(N,dtype='float32');echo=np.zeros((N,2),dtype='float32');throw_settings=[]
basic_send=bp(lead,450,5200)*activity
for i,end in enumerate(ends):
    start=max(0,round((end-.48)*SR));stop=min(N,round((end+.015)*SR));n=stop-start
    gate=np.zeros(N,dtype='float32');u=np.linspace(0,1,n)
    gate[start:stop]=np.sin(np.pi*u)**1.5;throw=np.maximum(throw,gate)
    phrase=basic_send*gate;tau=(2 if i%2==0 else 3)*60/135/2
    for repeat,level in enumerate([1.,.24,.07],start=1):
        y=shift(phrase,repeat*tau)
        if repeat>1:y=bp(y,600,3600)
        first_left=(i+repeat)%2==0;pan=[.98,.20] if first_left else [.20,.98]
        echo+=y[:,None]*np.asarray(pan,dtype='float32')[None,:]*level
    throw_settings.append({'end_s':end,'interval_ms':tau*1000})
echo_unscaled=echo.copy();source_mask=throw>.1
em=np.max(abs(echo),axis=1);echo_mask=em>np.max(em)*.01
echo*=rms(lead[source_mask])*10**(-16.5/20)/max(rms(echo[echo_mask]),1e-9)
echo*=10**(-6*activity[:,None]/20)
write(echo,O/'echo.f32');del echo_unscaled

# Two distinct depths: short diffuse support; longer tails only from phrase endings.
rng=np.random.default_rng(20261018)
def tail(source,decay_low,decay_high,predelay,lo,hi):
    length=round((decay_low+.25)*SR);t=np.arange(length)/SR;out=[]
    common=rng.standard_normal(length)
    for channel in range(2):
        n=.12*common+np.sqrt(1-.12**2)*rng.standard_normal(length)
        h=bp(n,lo,1800)*np.exp(-6.9078*t/decay_low)+.65*bp(n,1800,hi)*np.exp(-6.9078*t/decay_high)
        h*=1-np.exp(-t/.025);h=np.r_[np.zeros(round(predelay*SR)),h];h/=np.sqrt(np.sum(h*h))
        out.append(signal.oaconvolve(source,h)[:N])
    return np.column_stack(out).astype('float32')
shallow=tail(bp(lead,600,6500)*activity,.65,.45,.040,600,6500)
shallow*=lr*10**(-26/20)/max(rms(shallow[active]),1e-9)
shallow*=10**(-3*activity[:,None]/20)
deep=tail(basic_send*throw,1.55,1.05,.075,550,6500)
dm=np.max(abs(deep),axis=1);deep_mask=dm>np.max(dm)*.01
deep*=rms(lead[source_mask])*10**(-22/20)/max(rms(deep[deep_mask]),1e-9)
deep*=10**(-5*activity[:,None]/20)
write(shallow,O/'shallow.f32');write(deep,O/'deep.f32')
fx=doubles+echo+shallow+deep
fx_ratio=20*np.log10(rms(fx[active])/lr);cap=min(1.,10**((-11-fx_ratio)/20));fx*=cap
write(core+fx,O/'vocal_unmatched.f32');vm=measure(O/'vocal_unmatched.f32')
vg=float(ref['input_i'])+.55-float(vm['input_i']);factor=10**(vg/20)
write(core*factor,O/'core_mix.f32');write(fx*factor,O/'fx_mix.f32');write((core+fx)*factor,O/'vocal.f32')
write(arr(C/'beat_clean.f32')+arr(O/'vocal.f32'),O/'premaster.f32')
print('PREMASTER_READY',json.dumps({'vocal_gain_dB':vg,'fx_RMS_relative_lead_dB':fx_ratio,'fx_cap':cap}),flush=True)

target=-11.5;pre=measure(O/'premaster.f32');gain=target-float(pre['input_i']);passes=[]
for i in range(5):
    raw(O/'premaster.f32',O/'master.f32',f'volume={gain:.7f}dB,aresample=192000,alimiter=limit={10**(-1.4/20):.10f}:attack=5:release=80:level=0:latency=1,aresample=48000')
    m=measure(O/'master.f32');passes.append({'gain_dB':gain,'LUFS':float(m['input_i']),'dBTP':float(m['input_tp'])});delta=target-float(m['input_i'])
    if abs(delta)<.05:break
    gain+=delta
stats=gain_stats(O/'premaster.f32',O/'master.f32',10**(gain/20))
assert abs(float(m['input_i'])-target)<.12 and float(m['input_tp'])<-1.1
assert stats['gain_reduction_dB_percentiles']['95']<3.0 and stats['active_percent_over_3dB']<4
master=arr(O/'master.f32');vocal=arr(O/'vocal.f32')
assert len(master)==N and np.isfinite(master).all() and abs(master).max()<1
mono=float(10*np.log10(np.mean(master.mean(1)**2)/np.mean(master**2)));assert mono>-.8
mid=vocal.mean(1);side=(vocal[:,0]-vocal[:,1])/2
width={name:float(20*np.log10(rms(side[mask])/rms(mid[mask]))) for name,mask in [('all_active',active),('sustained_vowels',vowel_samples)]}
assert width['all_active']<-8 and width['sustained_vowels']<-8

for name,source in [('MUSIC_v11_1CALL',O/'master.f32'),('MUSIC_v11_VOCAL',O/'vocal.f32'),('MUSIC_v11_VOCAL_CORE',O/'core_mix.f32'),('MUSIC_v11_VOCAL_FX',O/'fx_mix.f32')]:
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(source),'-c:a','pcm_s24le',str(O/(name+'.wav'))],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(O/'MUSIC_v11_1CALL.wav'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v11_1CALL.mp3')],check=True)
mp=measure(O/'MUSIC_v11_1CALL.mp3',False);assert float(mp['input_tp'])<-.5

# Same performance, matched level: V9 then V11, with both mix and vocal comparisons.
parts=[];comparison=[]
for label,path,start,end,target_lufs in [('V9_MIX',C/'MUSIC_v9_CLEAN.f32',60,76,-16),('V11_MIX',O/'master.f32',60,76,-16),
                                      ('V9_VOCAL',C/'clean_vocal.f32',100,110,-20),('V11_VOCAL',O/'vocal.f32',100,110,-20)]:
    y=np.array(arr(path)[start*SR:end*SR]);fade=np.linspace(0,1,384);y[:384]*=fade[:,None];y[-384:]*=fade[::-1,None]
    temp=O/(label+'.f32');write(y,temp);mclip=measure(temp);g=target_lufs-float(mclip['input_i']);y*=10**(g/20);assert abs(y).max()<.99
    at=sum(len(a) for a in parts)/SR;comparison.append({'label':label,'start_s':at,'end_s':at+len(y)/SR,'target_LUFS':target_lufs,'gain_dB':g})
    parts.extend([y,np.zeros((SR//2,2),'float32')])
write(np.concatenate(parts[:-1]),O/'comparison.f32')
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','2','-i',str(O/'comparison.f32'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v11_COMPARE.mp3')],check=True)
np.savez(O/'controls.npz',times=times,activity=act,voiced=voiced,drydb=drydb)
result={'source':'V7 original tuned lead; V9 accompaniment; no V10 reconstructed audio, no reference-song samples',
 'intent':'Vocal beautification with light tone finishing, subtle nonlinear color and phrase-dependent backing/space',
 'static_EQ':static_eq,'dynamic_EQ':dynamic,'core_loudness_compensation_dB':core_gain,
 'harmonic_color':{'band_Hz':[220,2400],'residual_band_Hz':[250,5200],'oversampling':4,'relative_active_RMS_dB':-32,'nonlinearity':'tanh with .08 offset; input-proportional component removed by least squares; selected voiced spans only'},
 'backing':{'cents':[-6,7],'delay_ms':[31,49],'band_Hz':[420,6100],'vowel_minimum_span_ms':350,'skip_onset_ms':60,'fade_in_ms':120,'fade_out_ms':90,'selected_seconds_over_half':float(np.sum(vowel>.5)/SR),'regions':regions,'sample_counts':pitch_lengths,'channel_RMS_relative_selected_lead_dB':-11.5},
 'space':{'throws':throw_settings,'echo_decay_gains':[1,.24,.07],'echo_relative_selected_RMS_dB':-16.5,'echo_duck_dB':6,'short_tail':{'predelay_ms':40,'low_T60_s':.65,'high_T60_s':.45,'active_relative_RMS_dB':-26,'duck_dB':3},'end_tail':{'predelay_ms':75,'low_T60_s':1.55,'high_T60_s':1.05,'selected_RMS_dB':-22,'duck_dB':5}},
 'levels':{'vocal_target_LUFS':float(ref['input_i'])+.55,'vocal_post_FX_gain_dB':vg,'FX_cap':cap,'FX_active_RMS_before_cap_dB':fx_ratio,'vocal_side_mid_dB':width},
 'master':{'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),'MP3_LUFS':float(mp['input_i']),'MP3_dBTP':float(mp['input_tp']),'limiter':stats,'passes':passes,'mono_fold_energy_dB':mono,'duration_seconds':N/SR},
 'comparison':comparison,'limitations':'No subjective audition. Reference-separated vocal is approximate and was only analysed, not mixed into this audio. No claim of identifying original artist plugin settings or reproducing vocal anatomy. Synthetic backing is not a separately performed double. V7 includes previously printed effects, also present in CORE.'}
(O/'validation.json').write_text(json.dumps(result,indent=2));print('COMPLETE',json.dumps(result),flush=True)
