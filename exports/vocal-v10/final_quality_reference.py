from pathlib import Path
exec(Path('/workspace/audio-v8-reference/compare.py').read_text().split('out={}')[0])
old=json.loads(Path('/workspace/audio-v8-reference/vocal_comparison.json').read_text())
results={};deltas={}
for a,b in [(40,70),(100,130)]:
 key=f'{a}_{b}';ref=old[f'reference_estimated_vocal_{key}'];results['reference_'+key]=ref
 for label,path in [('V10','/workspace/audio-rebuild/vocal.f32'),('V10core','/workspace/audio-rebuild/core.f32'),('V9','/workspace/audio-clean/clean_vocal.f32'),('dry','/workspace/audio-analysis/dry.f32')]:
  v=np.memmap(path,dtype=np.float32,mode='r').reshape(-1,2);r=metrics(v[a*FS:b*FS].copy());results[label+'_'+key]=r
  deltas[label+'_minus_ref_'+key]={name:{band:round(v-ref[name][band],3) for band,v in r[name].items()} for name in ['mid_band_dB_relative_300_5000','mid_band_dB_top_half_frames']}
def finite_json(o):
 if isinstance(o,dict):return {k:finite_json(v) for k,v in o.items()}
 if isinstance(o,list):return [finite_json(v) for v in o]
 if isinstance(o,float) and not np.isfinite(o):return None
 return o
Path('/workspace/audio-v10-review/final_quality_reference.json').write_text(json.dumps(finite_json({'metrics':results,'deltas':deltas}),indent=2,allow_nan=False))
print(json.dumps(deltas,indent=2))
