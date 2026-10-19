"""V2C: replace two external reverb returns; retain V2B lead/beat balance.

CORE already contains printed ambience. These returns are production layers,
not an estimate or inversion of the recording room. No reference audio used.
"""
from pathlib import Path
import json, hashlib
import numpy as np
from scipy import signal

P=Path('/workspace/audio-v2-candidate')
B=Path('/workspace/audio-v2b-balance')
O=Path('/workspace/audio-v2c-space');O.mkdir(exist_ok=True)
SR=48000;H=240
def arr(p):return np.memmap(p,dtype='float32',mode='r').reshape(-1,2)
def write(x,p):np.asarray(x,dtype='float32').tofile(p)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def rms(x):return float(np.sqrt(np.mean(np.asarray(x,dtype='float64')**2)))
def band(x,lo,hi):
    return signal.sosfilt(signal.butter(2,[lo,hi],fs=SR,btype='bandpass',output='sos'),x,axis=0).astype('float32')
def smooth(v,attack,release):
    y=np.empty_like(v);z=float(v[0])
    for i,w in enumerate(v):
        a=np.exp(-.005/(attack if w>z else release));z=a*z+(1-a)*w;y[i]=z
    return y

core=arr(P/'core_mix.f32');N=len(core);sample_times=np.arange(N)/SR
c=np.load(P/'controls.npz');t=c['times']
def interp(x):return np.interp(sample_times,t,x).astype('float32')
activity=interp(c['activity']);voiced=interp(c['voiced']);entry=interp(c['entry'])
active=interp((c['drydb']>-38).astype('float32'))>.9
lead=core.mean(1);lead_rms=rms(core[active])

# A short recovery lets the return open at phrase ends, while the entrance
# envelope protects the beginning of the next line. Interpolation avoids steps.
duck_control=smooth(np.clip((c['drydb']+44)/10,0,1),.008,.145)
duck=interp(duck_control)
send_gate=activity
plate_weight=interp(smooth(.35+.65*c['voiced'],.065,.140))
rng=np.random.default_rng(2026101903)

def make_ir(name,lo,hi,decay_low,decay_high,predelay,rise,correlation):
    # Independent noise in overlapping low/high bands avoids a coherent
    # crossover cancellation. A dense envelope avoids discrete small-room taps.
    n=round((decay_low+.3)*SR);tt=np.arange(n)/SR
    env_rise=1-np.exp(-tt/rise)
    final_fade=np.minimum(1,(n-1-np.arange(n))/(SR*.05))
    def field():
        low=band(rng.standard_normal(n),lo,2200)*np.exp(-6.907755*tt/decay_low)
        high=band(rng.standard_normal(n),1800,hi)*np.exp(-6.907755*tt/decay_high)
        h=(low+.62*high)*env_rise*final_fade
        return h/np.sqrt(np.sum(h*h))
    mid=field();side=field()
    # Orthogonalize the two diffuse fields before setting stereo correlation.
    side-=mid*np.dot(side,mid);side/=np.sqrt(np.sum(side*side))
    m=np.sqrt((1+correlation)/2);s=np.sqrt((1-correlation)/2)
    ir=np.column_stack([m*mid+s*side,m*mid-s*side])
    ir=np.pad(ir,((round(predelay*SR),0),(0,0))).astype('float32')
    write(ir,O/(name+'_ir.f32'))
    return ir

def render(name,source,config,target,duck_db,entry_db):
    ir=make_ir(name,**config)
    out=np.column_stack([signal.oaconvolve(source,ir[:,i])[:N] for i in range(2)]).astype('float32')
    gain_envelope=10**((-duck_db*duck-entry_db*entry)/20)
    out*=gain_envelope[:,None]
    calibration=lead_rms*10**(target/20)/rms(out[active]);out*=calibration
    assert np.isfinite(out).all()
    write(out,O/(name+'.f32'))
    print(name,{'active_relative_core_dB':20*np.log10(rms(out[active])/lead_rms),'calibration_dB':20*np.log10(calibration)},flush=True)
    return out,{'ir':config,'active_relative_core_target_dB':target,'return_duck_max_dB':duck_db,
                'extra_phrase_entry_duck_max_dB':entry_db,'calibration_dB':float(20*np.log10(calibration))}

short,short_spec=render('shallow',band(lead,390,6500)*send_gate,
    dict(lo=390,hi=6500,decay_low=.75,decay_high=.45,predelay=.022,rise=.010,correlation=.40),
    target=-26,duck_db=2,entry_db=1.0)
plate,plate_spec=render('deep',band(lead,500,6500)*send_gate*plate_weight,
    dict(lo=500,hi=6500,decay_low=1.6,decay_high=.95,predelay=.048,rise=.025,correlation=.15),
    target=-27,duck_db=4,entry_db=2.5)
reverb=short+plate;write(reverb,O/'reverb.f32')
fx=np.asarray(arr(P/'doubles.f32')+arr(P/'echo.f32')+reverb,dtype='float32')
write(fx,O/'fx_mix.f32')
vocal=np.asarray(core+fx,dtype='float32');write(vocal,O/'vocal.f32')
write(vocal+arr(B/'beat.f32'),O/'premaster.f32')
np.savez(O/'controls.npz',times=t,duck_control=duck_control,plate_weight=np.interp(t,sample_times,plate_weight))

regions={'active':active,'sustained':voiced>.65,'entry':entry>.5,
         'quiet_after_voice':(activity>.05)&(activity<.35)}
old_reverb=arr(P/'shallow.f32')+arr(P/'deep.f32')
levels={}
for label,x in [('V2B_reverb',old_reverb),('V2C_reverb',reverb),('V2B_vocal',arr(P/'vocal.f32')),('V2C_vocal',vocal)]:
    levels[label]={k:{'RMS_dBFS':float(20*np.log10(rms(x[m])+1e-20)),
                      'relative_CORE_dB':float(20*np.log10((rms(x[m])+1e-20)/(rms(core[m])+1e-20)))} for k,m in regions.items()}
reverb_lift=levels['V2C_reverb']['active']['RMS_dBFS']-levels['V2B_reverb']['active']['RMS_dBFS']
assert 4<reverb_lift<8

result={'version':'V2C space candidate','base_commit':'9c8f4ee55419e17fb517559cfedf1a63b0cd8d1c',
 'user_feedback':'V2B balance accepted; more and better reverb requested to seat the vocal.',
 'routing':'V2 CORE + V2 doubles + V2 echo + new shallow + new deep + exact V2B beat; then master bus.',
 'unchanged_sources':{str(p):sha(p) for p in [P/'core_mix.f32',P/'doubles.f32',P/'echo.f32',B/'beat.f32']},
 'changed_returns':'External shallow/deep returns replaced, not stacked on their old versions.',
 'shallow':short_spec,'deep':plate_spec,
 'send':'CORE Mid, bandpass, original-dry-informed activity. Deep weighted 0.35 + 0.65*selected sustained singing with 65/140ms smoothing.',
 'duck_detector':{'dry_level_range_dBFS':[-44,-34],'attack_ms':8,'release_ms':145},
 'levels':levels,'active_external_reverb_lift_dB':reverb_lift,
 'duration_s':N/SR,'sample_rate':SR,'seed':2026101903,
 'limits':'Signal-based production experiment, no subjective audition. CORE has printed ambience; reported reverb levels refer only to the external returns. IR decay constants are synthesis parameters, not room measurements.'}
(O/'space-design.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'reverb_lift_dB':reverb_lift,'levels':levels},indent=2),flush=True)
