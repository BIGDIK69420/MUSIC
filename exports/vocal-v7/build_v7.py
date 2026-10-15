from pathlib import Path
exec(Path('/workspace/audio-final/master_v3.py').read_text().split('# Control isolated wet-vocal spikes')[0])
O=Path('/workspace/audio-reference');V=Path('/workspace/audio-clarity');U=Path('/workspace/audio-unbox')
# Recover our own exact accompaniment, not a blind separation of the commercial reference.
b=array(V/'premaster.f32')-array(V/'vocal_mix_level.f32');b.astype('float32').tofile(O/'beat_before.f32')
runraw(O/'beat_before.f32',O/'beat_eq.f32','equalizer=f=260:t=q:w=0.85:g=-1.5,equalizer=f=1800:t=q:w=0.8:g=1,highshelf=f=6000:t=s:w=1:g=2.5')
b=array(O/'beat_eq.f32');mid=b.mean(1);side=(b[:,0]-b[:,1])/2
# Increase only existing side information; preserve bass and mono signal.
upper=signal.sosfilt(signal.butter(2,250,fs=sr,btype='highpass',output='sos'),side).astype('float32')
side=side+upper*(10**(5/20)-1)
np.column_stack([mid+side,mid-side]).astype('float32').tofile(O/'beat_wide.f32')
a=measure(O/'beat_before.f32');q=measure(O/'beat_wide.f32');bg=float(a['input_i'])-float(q['input_i']);runraw(O/'beat_wide.f32',O/'beat_final.f32',f'volume={bg:.7f}dB')
# Keep the V6 vocal, with a restrained upper-mid lift rather than more de-boxing.
runraw(U/'MUSIC_v6_OPEN_vocal.f32',O/'vocal_eq.f32','equalizer=f=1900:t=q:w=0.9:g=0.6')
a=measure(U/'MUSIC_v6_OPEN_vocal.f32');q=measure(O/'vocal_eq.f32');vg=float(a['input_i'])-float(q['input_i'])+.25
runraw(O/'vocal_eq.f32',O/'vocal_final.f32',f'volume={vg:.7f}dB')
(array(O/'vocal_final.f32')+array(O/'beat_final.f32')).astype('float32').tofile(O/'premaster.f32')
p=measure(O/'premaster.f32');gain=-12.08-float(p['input_i']);passes=[]
for i in range(4):
 runraw(O/'premaster.f32',O/'master.f32',f'volume={gain:.7f}dB,aresample=192000,alimiter=limit={10**(-1.25/20):.9f}:attack=5:release=80:level=0:latency=1,aresample=48000')
 m=measure(O/'master.f32');passes.append({'gain':gain,'LUFS':float(m['input_i']),'dBTP':float(m['input_tp'])});d=-12.08-float(m['input_i'])
 if abs(d)<.05:break
 gain+=d
x=array(O/'master.f32');assert len(x)==N and np.isfinite(x).all() and abs(x).max()<1
mono=float(10*np.log10(np.mean(x.mean(1)**2)/np.mean(x**2)));assert mono>-.8
stats=gain_stats(O/'premaster.f32',O/'master.f32',10**(gain/20));assert stats['gain_reduction_dB_percentiles']['95']<5
for name,path in [('MUSIC_v7_REFERENCE',O/'master.f32'),('MUSIC_v7_VOCAL',O/'vocal_final.f32')]:
 subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(path),'-c:a','pcm_s24le',str(O/(name+'.wav'))],check=True)
subprocess.run(['ffmpeg','-v','error','-y','-i',str(O/'MUSIC_v7_REFERENCE.wav'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v7_REFERENCE.mp3')],check=True)
mp=measure(O/'MUSIC_v7_REFERENCE.mp3',False);assert float(mp['input_tp'])<-.5
# Same 20-second passage, V6 then V7, each at -16 LUFS.
clips=[];comparison=[]
for name,path in [('V6',U/'MUSIC_v6_OPEN.f32'),('V7',O/'master.f32')]:
 c=np.array(array(path)[82*sr:102*sr]);tmp=O/(name+'_clip.f32');c.tofile(tmp);l=measure(tmp);g=-16-float(l['input_i']);c*=10**(g/20);fade=np.linspace(0,1,384);c[:384]*=fade[:,None];c[-384:]*=fade[::-1,None];clips+=[c,np.zeros((sr//2,2),'float32')];comparison.append({'name':name,'clip_gain_dB':g})
np.concatenate(clips[:-1]).astype('float32').tofile(O/'comparison.f32')
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(O/'comparison.f32'),'-c:a','libmp3lame','-b:a','320k',str(O/'MUSIC_v7_COMPARE.mp3')],check=True)
result={'reference':'User-supplied 1 Call.mp3 analysed as a complete mix, not separated or subjectively auditioned','changes':{'beat_EQ':'260Hz Q.85 -1.5dB; 1800Hz Q.8 +1dB; 6k shelf +2.5dB','beat_existing_side':'250Hz highpassed side added with coefficient 10^(5/20)-1; no synthetic delay. Phase-dependent transition, not an exact brickwall width boost.','beat_loudness_compensation_dB':bg,'vocal':'V6 OPEN + 1900Hz Q.9 +0.6dB, loudness matched then raised .25dB; no new reverb','vocal_gain_dB':vg},'passes':passes,'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),'MP3_LUFS':float(mp['input_i']),'MP3_dBTP':float(mp['input_tp']),'mono_fold_energy_dB':mono,'limiter':stats,'duration_seconds':N/sr,'comparison':comparison,'limitations':'Reference band levels include different instrumentation, arrangements and vocals; not an exact vocal EQ target. No claim of verified perceptual similarity.'}
(O/'validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
