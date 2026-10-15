"""Targeted, bounded de-boxing proposals from the user-approved V4.

No voice cloning, blind room inversion, or claim of subjective audition.
The original tuned vocal remains the only audible vocal source.
"""
from pathlib import Path
exec(Path('/workspace/audio-final/master_v3.py').read_text().split('# Control isolated wet-vocal spikes')[0])
from scipy import ndimage

O = Path('/workspace/audio-unbox')
V = Path('/workspace/audio-clarity')
H = 480  # 10 ms controls, interpolated to every sample
K = (N + H - 1) // H
times = (np.arange(K) + .5) * H / sr

def peak_sos(freq, q, db):
    a = 10 ** (db / 40)
    w = 2 * np.pi * freq / sr
    alpha = np.sin(w) / (2 * q)
    b = np.array([1 + alpha*a, -2*np.cos(w), 1-alpha*a])
    d = np.array([1 + alpha/a, -2*np.cos(w), 1-alpha/a])
    return np.r_[b/d[0], d/d[0]].reshape(1, 6)

def interp(v):
    return np.interp(np.arange(N)/sr, times, v).astype('float32')

def frame_power(v):
    v = np.pad(v, (0, K*H-len(v)))
    return np.mean(v.reshape(K, H).astype('float64')**2, axis=1)

def band_density(v, lo, hi):
    z = signal.sosfilt(signal.butter(2, [lo, hi], fs=sr, btype='bandpass', output='sos'), v)
    return ndimage.gaussian_filter1d(frame_power(z), 4) / (hi-lo)

def smooth_control(w, attack=.025, release=.150):
    out = np.empty_like(w)
    cur = float(w[0])
    for i, val in enumerate(w):
        a = np.exp(-.01/(attack if val > cur else release))
        cur = a*cur + (1-a)*val
        out[i] = cur
    return out

dryr = np.load(P/'dry_rms.npy')
drydb = np.interp(times, np.arange(len(dryr))*.04+.02, 20*np.log10(np.maximum(dryr, 1e-12)))
want = np.clip((drydb+52)/16, 0, 1)
held = np.empty_like(want)
cur, hold = 0., 0
for i, w in enumerate(want):
    if w >= cur:
        cur, hold = float(w), 8
    elif hold:
        hold -= 1
    else:
        cur = float(w) + (cur-float(w))*np.exp(-.01/.18)
    held[i] = cur
activity = interp(smooth_control(held, .008, .025))
active_frames = (held > .65) & (times > 6) & (times < 192)

original = array(V/'vocal_mix_level.f32')
mono = original.mean(axis=1)
detectors = []
for name, target, shoulders in [
    ('low_box', (350, 700), ((180, 320), (1050, 2000))),
    ('upper_box', (650, 1050), ((300, 550), (1400, 2300))),
]:
    p = band_density(mono, *target)
    ref = sum(band_density(mono, *band) for band in shoulders)/2
    prominence = 10*np.log10((p+1e-16)/(ref+1e-16))
    threshold = float(np.percentile(prominence[active_frames], 35))
    # The source's own percentile is an operating threshold, not an ideal vocal target.
    amt = smooth_control(np.clip((prominence-threshold)/5.5, 0, 1))
    amt *= held
    detectors.append((name, amt, {'frequency_band_Hz': target, 'reference_bands_Hz': shoulders,
        'prominence_threshold_dB': threshold, 'threshold_percentile': 35,
        'full_reduction_above_threshold_dB': 5.5,
        'active_control_percentiles': {str(q):float(np.percentile(amt[active_frames],q)) for q in [10,50,90,99]}}))
del mono

presets = {
    'MUSIC_v6_OPEN': {'static_525':-1.0, 'dynamic_525':-2.0, 'dynamic_820':-1.5,
        'presence_1500':.8, 'side_650':-3.5, 'side_active':.90, 'side_quiet':.62, 'mid_quiet':.88},
    'MUSIC_v6_DRIER': {'static_525':-1.3, 'dynamic_525':-2.8, 'dynamic_820':-2.2,
        'presence_1500':.9, 'side_650':-5., 'side_active':.79, 'side_quiet':.48, 'mid_quiet':.78},
}
ref_loud = measure(V/'vocal_mix_level.f32')
oldmix = array(V/'premaster.f32')
outputs = {}

for name, cfg in presets.items():
    print('START',name,flush=True)
    x = signal.sosfilt(peak_sos(525, 1.25, cfg['static_525']), original, axis=0).astype('float32')
    dynamic_stats = []
    for (detname, amt, stats), freq, q, db in zip(detectors, [525,820], [1.25,1.65], [cfg['dynamic_525'],cfg['dynamic_820']]):
        cut = signal.sosfilt(peak_sos(freq,q,db), x, axis=0).astype('float32')
        a = interp(amt)
        x += (cut-x)*a[:,None]
        # This is a fixed-cut/identity blend. At the centre frequency the gain is exact.
        centre = 20*np.log10(1+amt*(10**(db/20)-1))
        dynamic_stats.append(dict(stats, name=detname, centre_Hz=freq, Q=q,
            maximum_cut_dB=db, centre_gain_active_percentiles={str(j):float(np.percentile(centre[active_frames],j)) for j in [1,10,50,90]}))
        del cut,a
    x = signal.sosfilt(peak_sos(1500,.85,cfg['presence_1500']),x,axis=0).astype('float32')
    mid = x.mean(axis=1)
    side = (x[:,0]-x[:,1])*.5
    del x
    side = signal.sosfilt(peak_sos(650,.65,cfg['side_650']),side).astype('float32')
    # Lower the low-mid stereo ambience and gentle between-phrase overhang.
    # The mid/side signals are not assumed to be separated direct sound and room.
    mid *= cfg['mid_quiet']+(1-cfg['mid_quiet'])*activity
    side *= cfg['side_quiet']+(cfg['side_active']-cfg['side_quiet'])*activity
    un = O/(name+'_vocal_unmatched.f32')
    np.column_stack([mid+side,mid-side]).astype('float32').tofile(un)
    del mid,side
    vm = measure(un)
    vg = float(ref_loud['input_i'])-float(vm['input_i'])
    vp = O/(name+'_vocal.f32')
    runraw(un,vp,f'volume={vg:.7f}dB')
    vocal_measure = measure(vp)
    assert abs(float(vocal_measure['input_i'])-float(ref_loud['input_i']))<.12

    vocal = array(vp)
    prem = O/(name+'_premaster.f32')
    mix = np.memmap(prem,dtype='float32',mode='w+',shape=(N,2))
    for st in range(0,N,sr*10):
        en = min(N,st+sr*10)
        mix[st:en] = oldmix[st:en]-original[st:en]+vocal[st:en]
    mix.flush()
    del mix
    pre = measure(prem)
    gain = -12.08-float(pre['input_i'])
    dest = O/(name+'.f32')
    passes = []
    for _ in range(4):
        runraw(prem,dest,f'volume={gain:.7f}dB,aresample=192000,alimiter=limit={10**(-1.25/20):.9f}:attack=5:release=80:level=0:latency=1,aresample=48000')
        m = measure(dest)
        passes.append({'gain_dB':gain,'LUFS':float(m['input_i']),'dBTP':float(m['input_tp'])})
        delta = -12.08-float(m['input_i'])
        if abs(delta)<.045:
            break
        gain += delta
    assert abs(float(m['input_i'])+12.08)<.12
    assert float(m['input_tp']) < -1.0
    limiting = gain_stats(prem,dest,10**(gain/20))
    assert limiting['gain_reduction_dB_percentiles']['95'] < 5
    assert limiting['active_percent_over_3dB'] < 5
    y = array(dest)
    assert len(y)==N and np.isfinite(y).all() and np.max(abs(y))<1
    mono_loss = float(10*np.log10(np.mean(y.mean(axis=1)**2)/np.mean(y**2)))
    assert mono_loss>-.5
    wav,mp3 = O/(name+'.wav'),O/(name+'.mp3')
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(dest),'-c:a','pcm_s24le',str(wav)],check=True)
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(wav),'-c:a','libmp3lame','-b:a','320k',str(mp3)],check=True)
    enc = measure(mp3,False)
    assert float(enc['input_tp'])<-.5
    subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar','48000','-ac','2','-i',str(vp),'-c:a','pcm_s24le',str(O/(name+'_VOCAL.wav'))],check=True)
    outputs[name] = {'settings':cfg,'dynamic_bands':dynamic_stats,'stem_loudness_compensation_dB':vg,
        'stem_LUFS':float(vocal_measure['input_i']),'WAV_LUFS':float(m['input_i']),'WAV_dBTP':float(m['input_tp']),
        'MP3_LUFS':float(enc['input_i']),'MP3_dBTP':float(enc['input_tp']),'duration_seconds':N/sr,
        'mono_fold_energy_dB':mono_loss,'limiter':limiting,'passes':passes}
    print('DONE',name,json.dumps(outputs[name]),flush=True)

validation = {'source':'V4 tuned, aligned vocal; V4 premaster accompaniment retained exactly before the new master limiter',
    'approach':'Broad bounded low-mid dynamic cuts, small 1500Hz lift, frequency-selective side reduction; no new reverb/delay/saturation or raw/tuned doubling',
    'reference_file_status':'1 Call.wav upload exceeds the available download tool 32 MiB limit; not accessed or analysed',
    'controls':'10 ms measurements, 40 ms power smoothing, 25 ms attack / 150 ms release, sample-interpolated linked stereo EQ; original dry only controls activity',
    'outputs':outputs,'limitations':['No subjective audition; these are targeted proposals, not a verified removal of perceived boxiness.',
        'Existing printed room and direct voice cannot be uniquely separated from these files.',
        'The dynamic-band operating threshold is internal to this recording, not a measured professional-reference target.']}
(O/'validation.json').write_text(json.dumps(validation,indent=2))
print('COMPLETE',flush=True)
