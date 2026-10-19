from pathlib import Path
import json,numpy as np
O=Path('/workspace/audio-v2-review-master');SR=48000
arr=lambda p:np.memmap(p,'float32','r').reshape(-1,2)
A={v:{n:arr(Path(p)/(n+'.f32')) for n in ['premaster','master']} for v,p in [('V1','/workspace/audio-v13'),('V2','/workspace/audio-v2-candidate')]};D={'V1':5.74,'V2':5.73}
events=json.load(open(O/'peak-candidates.json'))['candidates'];out=[]
for ev in events:
 c=ev['beat_actual_sample_peak_time_s'];start=int((c-.030)*SR);end=int((c+.150)*SR);row={'center_s':c,'window_s':[c-.030,c+.150]}
 for v in A:
  x=np.asarray(A[v]['premaster'][start:end],dtype='float64')*10**(D[v]/20);y=np.asarray(A[v]['master'][start:end],dtype='float64');ip=np.mean(x*x,axis=1);op=np.mean(y*y,axis=1)
  xx=np.r_[0,np.cumsum(ip)];yy=np.r_[0,np.cumsum(op)]
  row[v]={'driven_input_sample_peak_dBFS':float(20*np.log10(np.max(abs(x)))),'output_sample_peak_dBFS':float(20*np.log10(np.max(abs(y)))),'whole_event_input_output_energy_attenuation_dB':float(10*np.log10(np.mean(ip)/np.mean(op))),'short_window_energy_attenuation':{}}
  for ms in [5,10,20]:
   h=int(ms*.001*SR);i=np.arange(0,len(x)-h,48);a=xx[i+h]-xx[i];b=yy[i+h]-yy[i];valid=a/h>1e-5;atten=10*np.log10(a[valid]/np.maximum(b[valid],1e-20));row[v]['short_window_energy_attenuation'][str(ms)]={'maximum_dB':float(np.max(atten)),'p95_dB':float(np.percentile(atten,95)),'median_dB':float(np.median(atten))}
 row['driven_peak_change_dB']=row['V2']['driven_input_sample_peak_dBFS']-row['V1']['driven_input_sample_peak_dBFS'];row['whole_event_attenuation_change_dB']=row['V2']['whole_event_input_output_energy_attenuation_dB']-row['V1']['whole_event_input_output_energy_attenuation_dB']
 row['maximum_energy_attenuation_change_dB']={str(ms):row['V2']['short_window_energy_attenuation'][str(ms)]['maximum_dB']-row['V1']['short_window_energy_attenuation'][str(ms)]['maximum_dB'] for ms in [5,10,20]}
 out.append(row)
def summary(v):
 return {'minimum_dB':float(np.min(v)),'median_dB':float(np.median(v)),'maximum_dB':float(np.max(v)),'number_decreased_over005dB':int(np.sum(np.array(v)<-.05)),'number_increased_over005dB':int(np.sum(np.array(v)>.05))}
s={'driven_peak_change':summary([r['driven_peak_change_dB'] for r in out]),'whole_event_energy_attenuation_change':summary([r['whole_event_attenuation_change_dB'] for r in out]),'short_window_maximum_energy_attenuation_change':{str(ms):summary([r['maximum_energy_attenuation_change_dB'][str(ms)] for r in out]) for ms in [5,10,20]}}
r={'method':'Independent of least-squares gain proxy: stereo input/output power ratios in overlapping 5/10/20ms windows with1ms hop, and actual driven premaster sample peaks, in each repair center -30/+150ms. These are effective energy attenuations, not limiter internal state. Input/output filtering and within-window gain weighting remain relevant. No subjective audition.','summary':s,'events':out};(O/'qa_v2_proxy_check.json').write_text(json.dumps(r,indent=2));print(json.dumps(s,indent=2))
