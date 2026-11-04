import {VoiceDirection} from './VoiceDirection';
import {VoiceOptions} from './VoiceOptions';
import {useEffect,useState} from 'react';
import {Sun,Moon,Sparkles,Compass,Hash,Layers,RefreshCw,ArrowRight,ExternalLink} from 'lucide-react';
import {api} from './api';

export const flowNames={tarot:'Tarot',western:'Western astrology',chinese:'Chinese astrology',numerology:'Numerology',combined:'Combined'};
const icons={tarot:Sparkles,western:Sun,chinese:Compass,numerology:Hash,combined:Layers};
export function OutputControls({value,change,config,duration=true}) {
 return <div className="daily-output-fields">
  <label>Visual style<select aria-label="Visual style" value={value.style} onChange={e=>change('style',e.target.value)}><option value="esoteric-minimal">Esoteric Minimal</option><option value="storybook-cartoon">Storybook Cartoon</option></select></label>
  {duration?<label>Length<select aria-label="Daily video length" value={value.duration} onChange={e=>change('duration',Number(e.target.value))}>{[30,45,60,90].map(n=><option key={n} value={n}>{n} seconds</option>)}</select></label>:null}
  <label>Voice<select aria-label="Daily voice" value={value.voice} onChange={e=>change('voice',e.target.value)}><VoiceOptions config={config}/></select></label>
  <label>Writing<select aria-label="Daily writing" value={value.writer} onChange={e=>change('writer',e.target.value)}><option value="local">Built-in · free</option><option value="openai" disabled={!config.openai}>OpenAI · creative</option></select></label>
  <VoiceDirection value={value} change={change} config={config}/>
 </div>;
}

export function DailyStudio({config,onCreate,busy}) {
 const [form,setForm]=useState({daily:true,reading_type:'combined',date:config.today,edition:'morning',timezone:'America/Denver',style:'esoteric-minimal',deck:'esoteric-minimal',spread:'one',components:['tarot','western','chinese','numerology'],duration:90,voice:config.default_voice||'silent',writer:config.openai?'openai':'local',voice_style:'engaging',voice_energy:'expressive',include_news:false,news_selection:[0]});
 const [context,setContext]=useState(null),[loading,setLoading]=useState(false),[error,setError]=useState('');
 const [cards,setCards]=useState([]),[family,setFamily]=useState('western');
 const change=(key,value)=>{setForm(f=>({...f,[key]:value}));if(['date','edition','timezone','include_news'].includes(key))setContext(null);};
 const choose=kind=>{setForm(f=>({...f,reading_type:kind,duration:kind==='combined'?90:kind==='numerology'?45:60,spread:kind==='tarot'?'three':'one'}));if(['western','chinese','numerology'].includes(kind))setFamily(kind);};
 useEffect(()=>{let active=true;api('/daily/cards?style='+form.style).then(r=>{if(active)setCards(r.cards);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[form.style]);
 const review=async()=>{setLoading(true);setError('');try{setContext(await api('/daily/context','POST',form));}catch(e){setError(e.message);}finally{setLoading(false);}};
 const parts=form.reading_type==='combined'?form.components:[form.reading_type];
 return <div className="daily-page">
  <div className="flow-tabs" role="tablist" aria-label="Daily reading types">{Object.entries(flowNames).map(([key,name])=>{const Icon=icons[key];return <button key={key} role="tab" aria-selected={form.reading_type===key} className={form.reading_type===key?'selected':''} onClick={()=>choose(key)}><Icon size={19}/><span>{name}</span></button>;})}</div>
  {error?<p className="daily-error" role="alert">{error}</p>:null}
  <div className="daily-builder">
   <section className="panel daily-form"><h2>{flowNames[form.reading_type]}</h2><p className="helper">A collective reading. No personal question or birth details needed.</p>
    <fieldset disabled={!!busy||loading}>
     <div className="daily-date-row"><label>Reading date<input aria-label="Reading date" type="date" min="1900-01-01" max="2099-12-31" value={form.date} onChange={e=>change('date',e.target.value)}/></label><label>Edition<select aria-label="Edition" value={form.edition} onChange={e=>change('edition',e.target.value)}><option value="morning">Morning · 6 AM</option><option value="evening">Evening · 6 PM</option></select></label></div>
     <p className="edition-purpose">{form.edition==='morning'?<Sun size={17}/>:<Moon size={17}/>} {form.edition==='morning'?'Intentions, perspective, and the day ahead.':'Reflection, release, and what to carry forward.'}</p>
     <label>Publication timezone<select aria-label="Publication timezone" value={form.timezone} onChange={e=>change('timezone',e.target.value)}>{['America/Denver','America/New_York','America/Los_Angeles','Europe/London','UTC'].map(z=><option key={z}>{z}</option>)}</select></label>
     {form.reading_type==='combined'?<div className="component-choices"><span>Include these systems</span>{Object.entries(flowNames).filter(([k])=>k!=='combined').map(([key,name])=><label key={key}><input type="checkbox" aria-label={'Include '+name} checked={form.components.includes(key)} onChange={e=>change('components',e.target.checked?[...form.components,key]:form.components.filter(c=>c!==key))}/>{name}</label>)}<small>Choose at least two. Each system gets its own visual card.</small></div>:null}
     {parts.includes('tarot')?<label>Tarot artwork<select aria-label="Daily tarot deck" value={form.deck} onChange={e=>change('deck',e.target.value)}>{config.decks.map(d=><option key={d.id} value={d.id} disabled={!d.ready}>{d.label}</option>)}</select></label>:null}
     {form.reading_type==='tarot'?<label>Tarot spread<select aria-label="Daily tarot spread" value={form.spread} onChange={e=>change('spread',e.target.value)}><option value="one">One card · daily focus</option><option value="three">Three cards · focus, notice, next step</option></select></label>:null}
     <OutputControls value={form} change={change} config={config}/>
     <label className="daily-check"><input type="checkbox" aria-label="Include current events" checked={form.include_news} onChange={e=>change('include_news',e.target.checked)}/>Include current events</label>
     <p className="small-note">Uses timestamped BBC World and UN News headlines when available. Sources are saved with the edition.</p>
    </fieldset>
    <button className="secondary review-context" disabled={loading||!!busy||!form.date||(form.reading_type==='combined'&&form.components.length<2)} onClick={review}><RefreshCw size={17} className={loading?'spin':''}/>{loading?'Calculating context…':context?'Refresh date & sources':'Review date & sources'}</button>
    <button className="primary generate-daily" disabled={!context||!!busy||loading} onClick={()=>onCreate({...form,context_id:context.id})}>{busy==='daily-generate'?'Writing your edition…':`Generate ${form.edition} reading`}<ArrowRight size={17}/></button>
   </section>
   <section className="panel daily-context"><div className="context-heading"><h2>Date & sources</h2>{context?<span>Snapshot saved</span>:null}</div>
    {!context?<div className="context-empty"><Compass size={36}/><h3>A reading grounded in its day.</h3><p>Review the date to calculate the sky, Chinese calendar, and day number. Optional headlines stay attached to their sources.</p></div>:<>
     <div className="context-date"><strong>{new Date(context.publication_time).toLocaleDateString(undefined,{timeZone:context.timezone,weekday:'long',month:'long',day:'numeric',year:'numeric'})}</strong><span>{form.edition==='morning'?'6:00 AM':'6:00 PM'} · {context.timezone}</span></div>
     {parts.includes('western')?<div className="fact-block"><h3>Western sky</h3><dl><dt>Sun</dt><dd>{context.western.positions.Sun.sign} · {context.western.positions.Sun.degree}°</dd><dt>Moon</dt><dd>{context.western.positions.Moon.sign} · {context.western.positions.Moon.degree}°</dd><dt>Lunar phase</dt><dd>{context.western.moon_phase} · {context.western.illumination}% lit</dd></dl>{context.western.aspects.map((a,i)=><p className="aspect" key={i}>{a.first} {a.aspect} {a.second} <span>{a.orb}° orb</span></p>)}<p className="small-note">Calculated tropical, geocentric positions at the edition time.</p></div>:null}
     {parts.includes('chinese')?<div className="fact-block"><h3>Chinese calendar</h3><dl><dt>Year</dt><dd>{context.chinese.year_element} {context.chinese.year_animal}</dd><dt>Day</dt><dd>{context.chinese.day_element} {context.chinese.day_animal} · {context.chinese.day_polarity}</dd><dt>Lunar date</dt><dd>{context.chinese.lunar_year} / {Math.abs(context.chinese.lunar_month)} / {context.chinese.lunar_day}{context.chinese.lunar_month<0?' (leap month)':''}</dd></dl><p className="small-note">Chinese New Year boundary; local calendar day. A collective reading.</p></div>:null}
     {parts.includes('numerology')?<div className="fact-block number-fact"><h3>Universal day</h3><strong>{context.numerology.number}</strong><p>{context.numerology.calculation}</p><p className="small-note">All date digits reduced; 11, 22, and 33 preserved. AM and PM share the same date number.</p></div>:null}
     {parts.includes('tarot')?<div className="fact-block"><h3>Tarot draw</h3><p className="helper">{form.reading_type==='tarot'&&form.spread==='three'?'Three cards':'One card'} will be drawn once for this date and edition. Rewriting preserves the draw.</p></div>:null}
     {form.include_news?<div className="fact-block"><h3>World context</h3>{context.news.headlines.length?context.news.headlines.map((h,index)=><div className="headline" key={h.url}><label><input type="checkbox" aria-label={'Use headline '+(index+1)} checked={form.news_selection.includes(index)} disabled={!form.news_selection.includes(index)&&form.news_selection.length>=3} onChange={e=>change('news_selection',e.target.checked?[...form.news_selection,index]:form.news_selection.filter(i=>i!==index))}/><span>{h.title}</span></label><a href={h.url} target="_blank" rel="noreferrer">{h.publisher} · {new Date(h.published).toLocaleString()} <ExternalLink size={11}/></a></div>):<p className="helper">{context.news.status}</p>}<p className="small-note">Headlines published before the snapshot cutoff, within 36 hours. Choose up to three.</p></div>:null}
     <p className="context-footnote">Calculated facts inform symbolic interpretation. The reading is for entertainment and reflection.</p>
    </>}
   </section>
  </div>
  <section className="daily-gallery panel"><div className="gallery-heading"><div><h2>Your visual card collection</h2><p className="helper">Matching artwork for each system, in both studio styles.</p></div><div className="gallery-filters">{['western','chinese','numerology'].map(key=><button key={key} className={family===key?'selected':''} onClick={()=>setFamily(key)}>{flowNames[key]}</button>)}</div></div>
   <div className="visual-grid">{cards.filter(c=>c.family===family).map(c=><figure key={c.id}>{c.ready?<img src={c.image_url} alt={c.name} loading="lazy"/>:<div className="art-pending">Artwork preparing</div>}<figcaption>{c.name}</figcaption></figure>)}</div>
  </section>
 </div>;
}
