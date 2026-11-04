import {useEffect,useRef,useState} from 'react';
import {api} from './api';

const styles={engaging:'Engaging host',uplifting:'Uplifting & enthusiastic',mystical:'Intriguing storyteller',grounded:'Warm & grounded',reflective:'Evening reflection'};
const energies={natural:'Natural',expressive:'Expressive',high:'High energy'};

export function VoiceDirection({value,change,config}) {
 const [busy,setBusy]=useState(false),[sample,setSample]=useState(null),[error,setError]=useState('');
 const sequence=useRef(0);
 useEffect(()=>{sequence.current++;setSample(null);setError('');},[value.voice,value.voice_style,value.voice_energy]);
 const listen=async()=>{const request=++sequence.current;setBusy(true);setError('');try{const result=await api('/voice/sample','POST',{voice:value.voice,voice_style:value.voice_style||'engaging',voice_energy:value.voice_energy||'expressive'});if(request===sequence.current)setSample(result);}catch(e){if(request===sequence.current)setError(e.message);}finally{setBusy(false);}};
 if(!value.voice?.startsWith('openai-'))return null;
 return <div className="voice-direction" style={{gridColumn:'1 / -1',padding:'12px 0'}}>
  <label>Voice delivery<select aria-label="Voice delivery" value={value.voice_style||'engaging'} onChange={e=>change('voice_style',e.target.value)}>{Object.entries(config.voice_styles||styles).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
  <label>Voice energy<select aria-label="Voice energy" value={value.voice_energy||'expressive'} onChange={e=>change('voice_energy',e.target.value)}>{Object.entries(config.voice_energies||energies).map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>
  <button type="button" className="secondary" disabled={busy||!config.openai} onClick={listen} style={{marginTop:12}}>{busy?'Preparing voice sample…':'Listen to voice sample'}</button>
  <p className="small-note">AI voice direction controls emphasis, inflection and pacing. Video length follows the spoken delivery. A new sample uses OpenAI credits; repeats are cached.</p>
  {sample?<audio key={sample.url} controls autoPlay src={sample.url} aria-label="AI voice sample" style={{width:'100%',marginTop:10}}/>:null}
  {error?<p role="alert" className="daily-error">{error}</p>:null}
 </div>;
}
