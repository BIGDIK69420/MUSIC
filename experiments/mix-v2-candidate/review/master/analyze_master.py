from pathlib import Path
import numpy as np
from scipy import signal, ndimage
import subprocess,re,json
O=Path('/workspace/audio-v2-review-master');SR=48000
P={'V1_master':Path('/workspace/audio-v13/master.f32'),'reference':Path('/workspace/audio-reference/reference.f32'),'V1_premaster':Path('/workspace/audio-v13/premaster.f32'),'V1_beat':Path('/workspace/audio-v13/beat.f32')}
bands=[(25,70),(70,140),(140,300),(300,700),(700,1500),(1500,3500),(3500,7000),(7000,14000)]
def arr(p):return np.memmap(p,'float32','r').reshape(-1,2)
def db(x):return 10*np.log10(np.maximum(x,1e-20))
def q(x):return {str(v):float(np.percentile(x,v)) for v in [10,50,90,95,99]}
def framepower(x,h=1920):
 n=len(x)//h*h;return np.mean(np.asarray(x[:n]).reshape(-1,h)**2,axis=1)
def loud(p):
 r=subprocess.run(['ffmpeg','-hide_banner','-nostats','-f','f32le','-ar','48000','-ac','2','-i',str(p),'-af','loudnorm=I=-16:TP=-1.4:LRA=8:print_format=json','-f','null','-'],capture_output=True,text=True,check=True)
 return json.loads(re.search(r'\{\s*"input_i".*?\}',r.stderr,re.S).group())
reports={};envelopes={}
for name,p in P.items():
 x=arr(p);n=len(x);lm=loud(p);g=10**((-16-float(lm['input_i']))/20);mid=x.mean(axis=1)*g;side=(x[:,0]-x[:,1])*.5*g
 t=(np.arange(n//1920)+.5)*.04;fp=framepower(mid)+framepower(side)
 region=(t>6)&(t<192) if name!='reference' else (t>20)&(t<200)
 mask=region&(db(fp)>-35)
 rmsdb=db(fp);maxp=np.max(np.abs(np.asarray(x[:len(t)*1920])).reshape(-1,1920,2),axis=(1,2))*g
 report={'loudness':{k:lm[k] for k in ['input_i','input_tp','input_lra']},'matched_to_LUFS':-16,'matched_gain_dB':20*np.log10(g),'whole_stereo_rms_dBFS':float(db(np.mean(x.astype('float64')**2)*g*g)),'whole_side_mid_dB':float(db(np.mean(side**2)/np.mean(mid**2))),'whole_mono_fold_energy_dB':float(db(np.mean(mid**2)/(np.mean(mid**2)+np.mean(side**2)))),'whole_LR_correlation':float(np.corrcoef(x[::10].T)[0,1]),'active_40ms_rms_percentiles_dBFS':q(rmsdb[mask]),'active_40ms_crest_percentiles_dB':q(20*np.log10(maxp[mask]+1e-20)-rmsdb[mask]),'bands':{},'segments':{}}
 env={}
 for lo,hi in bands:
  sos=signal.butter(3,[lo,hi],btype='bandpass',fs=SR,output='sos');bm=signal.sosfilt(sos,mid);bs=signal.sosfilt(sos,side)
  power=framepower(bm)+framepower(bs);sm=ndimage.uniform_filter1d(power,25,mode='nearest');env[f'{lo}-{hi}']=power
  report['bands'][f'{lo}-{hi}']={'active_rms_dBFS':float(db(np.mean(power[mask]))),'active_40ms_envelope_p90_p10_dB':float(np.percentile(db(power[mask]),90)-np.percentile(db(power[mask]),10)),'active_1s_envelope_p90_p10_dB':float(np.percentile(db(sm[mask]),90)-np.percentile(db(sm[mask]),10)),'active_side_mid_dB':float(db(np.mean(framepower(bs)[mask])/np.mean(framepower(bm)[mask])))}
  for a,b in ([(38,68),(104,134),(159,189)] if name!='reference' else [(40,70),(100,130),(150,180)]):
   z=(t>=a)&(t<b)&(db(fp)>-35);report['segments'].setdefault(f'{a}-{b}',{})[f'{lo}-{hi}']=float(db(np.mean(power[z])))
 reports[name]=report;envelopes[name]=dict(t=t,mask=mask,full=fp,**env)
 print('DONE',name,flush=True)
# Approximate actual limiter response using 1ms common gain, then aggregate each 40ms.
x=np.array(arr(P['V1_premaster']));y=arr(P['V1_master']);drive=10**(5.74/20);nn=len(x)//48*48
xb=x[:nn].reshape(-1,48,2)*drive;yb=np.asarray(y[:nn]).reshape(-1,48,2);ep=(xb*xb).sum((1,2));gain=(xb*yb).sum((1,2))/np.maximum(ep,1e-20);gr=-20*np.log10(np.clip(gain,1e-6,1));n40=len(gr)//40
m40=gr[:n40*40].reshape(-1,40).max(1);g40=gr[:n40*40].reshape(-1,40).mean(1)
env=envelopes['V1_premaster'];mk=env['mask'][:n40];out={'active_1ms_GR_dB':q(gr[ep/96>1e-5]),'max_GR_dB':float(gr.max()),'mean_40ms_GR_correlations':{},'band_fraction_when_GR_over3dB_vs_other':{},'largest_40ms_GR_times_s':[]}
for k in [f'{a}-{b}' for a,b in bands]:
 e=env[k][:n40];out['mean_40ms_GR_correlations'][k]=float(np.corrcoef(db(e[mk]),g40[mk])[0,1]);fraction=e/np.maximum(env['full'][:n40],1e-20);out['band_fraction_when_GR_over3dB_vs_other'][k]={'over3_dB_fraction':float(np.mean(fraction[mk&(m40>3)])),'under3_dB_fraction':float(np.mean(fraction[mk&(m40<=3)]))}
inds=np.argsort(m40)[::-1];chosen=[]
for i in inds:
 if all(abs(i-j)>25 for j in chosen):chosen.append(i)
 if len(chosen)>=12:break
out['largest_40ms_GR_times_s']=[{'time_s':float(env['t'][i]),'GR_dB':float(m40[i])} for i in chosen]
reports['limiter_associations']=out
reports['limits']='All observations are signal measurements, not subjective listening. Independent arrangements, different passages and full-mix tonal balance prevent treating the reference as an exact EQ/width/dynamic target. Band powers use 3rd-order Butterworth bandpasses and overlap at crossover points. Interior activity masks exclude low-energy tails; matched LUFS uses each complete file.'
(O/'master-analysis.json').write_text(json.dumps(reports,indent=2));np.savez(O/'envelopes.npz',**{name+'_'+k:v for name,e in envelopes.items() for k,v in e.items()})
print(json.dumps(reports,indent=2))
