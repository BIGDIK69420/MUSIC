from pathlib import Path
exec(Path('/workspace/audio-final/master_v3.py').read_text().split('# Control isolated wet-vocal spikes')[0])
O=Path('/workspace/audio-reference')
bands=[(80,150),(150,300),(300,600),(600,1200),(1200,2500),(2500,5000),(5000,10000),(10000,16000)]
out={}
for name,path in [('reference',O/'reference.f32'),('V4',Path('/workspace/audio-clarity/master.f32')),('V6',Path('/workspace/audio-unbox/MUSIC_v6_OPEN.f32'))]:
 x=array(path);m=x.mean(1);s=(x[:,0]-x[:,1])/2
 f,t,z=signal.stft(m,fs=sr,nperseg=4096,noverlap=2048);_,_,zs=signal.stft(s,fs=sr,nperseg=4096,noverlap=2048)
 p=abs(z)**2;ps=abs(zs)**2;e=p.sum(0);active=(e>np.percentile(e,35))&(t>5)&(t<len(x)/sr-5)
 mean=p[:,active].mean(1);side=ps[:,active].mean(1);norm=mean[(f>=300)&(f<5000)].sum()
 q=measure(path);b={};sm={}
 for lo,hi in bands:
  mask=(f>=lo)&(f<hi);b[f'{lo}-{hi}']=float(10*np.log10(mean[mask].sum()/norm));sm[f'{lo}-{hi}']=float(10*np.log10((side[mask].sum()+1e-20)/(mean[mask].sum()+1e-20)))
 out[name]={'duration':len(x)/sr,'loudness':q,'mid_band_dB_relative_300_5000':b,'band_side_mid_dB':sm,'active_frame_rms_p90_p10_dB':float(10*np.log10(np.percentile(e[active],90)/np.percentile(e[active],10))),'note':'Full commercial mix, not isolated voice; active frames selected by energy, not vocal detection.'}
 print(name,json.dumps(out[name]),flush=True)
(O/'analysis.json').write_text(json.dumps(out,indent=2))
