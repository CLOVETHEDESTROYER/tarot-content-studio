import {useEffect,useState} from 'react';

import {FolderOpen,Copy,Play,RefreshCw,Download,ArrowUpRight,Check,LoaderCircle} from 'lucide-react';

import {api} from './api';

import {OutputControls,flowNames} from './DailyStudio';

import './agent.css';



export function AgentHistory({config,open}) {

 const tomorrow=new Date(config.today+'T12:00:00Z');tomorrow.setUTCDate(tomorrow.getUTCDate()+1);

 const [data,setData]=useState(null),[folder,setFolder]=useState(''),[busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState(''),[prompt,setPrompt]=useState('');

 const [form,setForm]=useState({requestId:'tarot-week-'+tomorrow.toISOString().slice(0,10),startDate:tomorrow.toISOString().slice(0,10),days:7,morningType:'combined',eveningType:'tarot',style:'esoteric-minimal',deck:'esoteric-minimal',voice:config.default_voice||'silent',writer:'local',components:['tarot','western','chinese','numerology']});

 const [batchMode,setBatchMode]=useState('series'),[readingTypes,setReadingTypes]=useState(['western','chinese','numerology']),[editions,setEditions]=useState(['morning']);

 const [canBrowse,setCanBrowse]=useState(false);
 useEffect(()=>{const ready=()=>setCanBrowse(typeof window.pywebview?.api?.choose_exchange_folder==='function');ready();window.addEventListener('pywebviewready',ready);return()=>window.removeEventListener('pywebviewready',ready);},[]);

 const count=form.days*(batchMode==='series'?readingTypes.length*editions.length:2);

 const refresh=async initial=>{const value=await api('/agent');setData(value);if(initial)setFolder(value.settings.folder);};

 useEffect(()=>{refresh(true).catch(e=>setError(e.message));const timer=setInterval(()=>refresh(false).catch(()=>{}),3000);return()=>clearInterval(timer);},[]);

 const act=async(name,work)=>{if(busy)return;setBusy(name);setError('');setNotice('');try{await work();await refresh(false);}catch(e){setError(e.message);}finally{setBusy('');}};

 const prepare=()=>act('prepare',async()=>{const saved=await api('/agent','PUT',{folder,enabled:data.settings.enabled});setFolder(saved.settings.folder);setNotice('Tarot exchange prepared. ZenWave folders are unchanged.');});

 const browse=()=>act('browse',async()=>{const selected=await window.pywebview.api.choose_exchange_folder();if(selected){setFolder(selected);setNotice('Folder selected. Click Prepare exchange to save it.');}});

 const watch=()=>act('watch',async()=>{const saved=await api('/agent','PUT',{folder:data.settings.enabled?data.settings.folder:folder,enabled:!data.settings.enabled});setFolder(saved.settings.folder);setNotice(data.settings.enabled?'Inbox watching paused. Active batches finish.':'Inbox watching enabled while this studio is running.');});

 const firstTest=()=>act('test',async()=>{await api('/agent/first-test','POST',{});setNotice('Connection test requested. Its existing result is reused if already generated.');});

 const submit=()=>act('week',async()=>{await api('/agent/requests','POST',{schemaVersion:1,kind:'reading-week',requestId:'tarot-week-'+form.startDate,brief:`Generate ${form.days} days of collective morning intentions and evening reflections for review.`,...form,...(batchMode==='series'?{readingTypes,editions}:{editions:['morning','evening']}),timezone:'America/Denver',includeNews:false,requestedBy:'Studio operator',campaign:'daily-perspective'});setNotice('Weekly batch queued. Each calendar slot is prepared once.');});

 const resume=record=>act(record.id,async()=>{await api('/agent/requests/'+record.id+'/resume','POST',{});setNotice('Resuming unfinished editions; saved exports will be reused.');});

 const openReading=readingId=>act('open',async()=>{const [draft,library]=await Promise.all([api('/readings/'+readingId),api('/readings')]);await open(draft,library.jobs);});

 const copyPrompt=()=>act('copy',async()=>{const text=`Use my dedicated StarPower Tarot exchange folder (${data.settings.folder}) through your authorized local or synced-storage access. Keep ZenWave's exchange, schedules, requests and permissions unchanged. Read AGENT-INSTRUCTIONS.md, catalog.json and studio-info.json; verify the catalog checksum. If Status/first-test.json is complete, retrieve and verify its existing test video; otherwise atomically copy Examples/first-test.json into Requests/first-test.json and wait for completion. Replay that same request to prove it is reused. Never post or schedule the connection test. Report whether you can actually read/write requests and retrieve the finished MP4. For production, use stable reading-week requests with explicit dates and America/Denver times. Only retrieve complete batches, and treat proposedPublishAt as a proposal. Schedule/post production media only through my separately authorized intended Page, then write real returned post IDs/times to Reports. Never edit the studio database or assume the studio itself publishes.`;setPrompt(text);if(navigator.clipboard){await navigator.clipboard.writeText(text);setNotice('Muse connection prompt copied.');}else setNotice('Copy the connection prompt below.');});

 if(!data)return <div className="loading">{error?<p role="alert">{error}</p>:<><LoaderCircle className="spin"/>Opening history and agent jobs…</>}</div>;

 const latestReport=asset=>data.reports.find(report=>report.assetId===asset.id);

 return <div className="agent-page">

  {error?<p className="daily-error" role="alert">{error}</p>:null}{notice?<p className="agent-notice" role="status"><Check size={16}/>{notice}</p>:null}

  <div className="agent-intro"><div><h2>A week of readings. One handoff.</h2><p>Generate here, let Muse retrieve the videos, then keep the actual posting results alongside each day.</p></div><span>{data.settings.enabled?'Watching inbox':'Inbox paused'}</span></div>

  <div className="agent-config-grid"><section className="panel agent-exchange"><h2>Connect the exchange</h2><p className="helper">The same Requests → Status → Ready → Reports pattern as ZenWave. Use a separate Tarot folder.</p>

   <label>Tarot exchange folder<input aria-label="Tarot exchange folder" disabled={data.settings.enabled} value={folder} onChange={e=>setFolder(e.target.value)}/></label>

   <div className="agent-buttons"><button className="secondary" disabled={!!busy||data.settings.enabled||!canBrowse} onClick={browse} title={canBrowse?'Choose a local or Google Drive Desktop folder':'Folder browsing is available in the desktop app'}><FolderOpen size={16}/>Browse folders</button><button className="secondary" disabled={!!busy} onClick={prepare}>Prepare exchange</button><button className="primary" disabled={!!busy} onClick={watch}>{data.settings.enabled?'Pause inbox':'Watch inbox'}</button></div>

   <p className="small-note">For Google Drive, open Google Drive for desktop and wait for its folder to appear in File Explorer or Finder. Choose a dedicated Tarot folder there, not a drive.google.com link. The drive letter can differ on each computer. The studio and computer must stay running; preparing a folder does not verify that Muse can access it.</p>

   <div className="agent-buttons"><button className="secondary" disabled={!!busy} onClick={firstTest}><Play size={16}/>Run connection test</button><button className="secondary" disabled={!!busy} onClick={copyPrompt}><Copy size={16}/>Copy Muse connection prompt</button></div>

   <p className="small-note">The 30-second test never claims a production date or authorizes posting. Verify Muse can retrieve it before relying on the connection.</p>

   {prompt?<label>Connection prompt<textarea aria-label="Muse connection prompt" readOnly value={prompt}/></label>:null}

  </section><section className="panel agent-week"><h2>Prepare a weekly batch</h2><p className="helper">Choose separate daily series, or one reading for each morning/evening slot. Targets use America/Denver.</p>

   <label>Batch layout<select aria-label="Weekly batch layout" value={batchMode} onChange={e=>setBatchMode(e.target.value)}><option value="series">Separate reading series</option><option value="editions">One morning and one evening reading</option></select></label>

   {batchMode==='series'?<fieldset className="agent-series"><legend>Daily reading series</legend>{Object.entries(flowNames).map(([key,name])=><label key={key}><input type="checkbox" checked={readingTypes.includes(key)} onChange={e=>setReadingTypes(v=>e.target.checked?[...v,key]:v.filter(k=>k!==key))}/>{name}</label>)}<label>Daily times<select aria-label="Weekly edition times" value={editions.length===2?'both':editions[0]} onChange={e=>setEditions(e.target.value==='both'?['morning','evening']:[e.target.value])}><option value="morning">Morning · 6 AM</option><option value="evening">Evening · 6 PM</option><option value="both">Morning and evening</option></select></label></fieldset>:null}

   <div className="agent-week-fields"><label>First day<input aria-label="Weekly first day" type="date" value={form.startDate} min="1900-01-01" max="2099-12-25" onChange={e=>setForm(f=>({...f,startDate:e.target.value,requestId:'tarot-week-'+e.target.value}))}/></label><label>Days<select aria-label="Weekly days" value={form.days} onChange={e=>setForm(f=>({...f,days:Number(e.target.value)}))}>{[1,2,3,4,5,6,7].map(n=><option key={n} value={n}>{n} day{n>1?'s':''} · {n*(batchMode==='series'?readingTypes.length*editions.length:2)} readings</option>)}</select></label>

   {batchMode==='editions'?['morning','evening'].map(slot=><label key={slot}>{slot==='morning'?'Morning reading':'Evening reading'}<select aria-label={'Weekly '+slot+' type'} value={form[slot+'Type']} onChange={e=>setForm(f=>({...f,[slot+'Type']:e.target.value}))}>{Object.entries(flowNames).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label>):null}</div>

   <label>Request ID<input aria-label="Weekly request ID" value={form.requestId} onChange={e=>setForm(f=>({...f,requestId:e.target.value}))}/></label>

   <label>Tarot artwork<select aria-label="Weekly tarot deck" value={form.deck} onChange={e=>setForm(f=>({...f,deck:e.target.value}))}>{config.decks.map(d=><option key={d.id} value={d.id} disabled={!d.ready}>{d.label}</option>)}</select></label>

   <OutputControls value={form} change={(key,value)=>setForm(f=>({...f,[key]:value}))} config={config} duration={false}/>

   <p className="small-note">Calculated sky and calendar context for each day. Generate news-based editions nearer publication, when headlines are available.</p>

   <button className="primary" disabled={!!busy||!form.startDate||count===0} onClick={submit}>{busy==='week'?<LoaderCircle className="spin" size={16}/>:<Play size={16}/>}Generate {count} readings</button>

  </section></div>

  <section className="panel agent-requests"><div className="gallery-heading"><div><h2>Agent jobs</h2><p className="helper">Stable request IDs preserve each brief, dated editions, and completed exports.</p></div><button className="secondary" disabled={!!busy} onClick={()=>act('poll',async()=>{await api('/agent/poll','POST',{});})}><RefreshCw size={15}/>Check inbox now</button></div>

   {!data.requests.length?<div className="agent-empty">No requests yet. Start with the connection test, or generate a weekly batch.</div>:data.requests.map(record=><article className="agent-request" key={record.id}><div><strong>{record.id}</strong><small>{record.request.kind==='connection-test'?'Connection test · never post':`${record.request.startDate} · ${record.items.length} dated readings`}</small><span>{record.request.brief}</span></div><div className={'agent-job-status status-'+record.status}><strong>{record.status==='complete'?'Ready for Muse':record.status}</strong><small>{record.progress||0}%{record.error?' · '+record.error:''}</small>{record.status==='running'?<progress max="100" value={record.progress||0}/>:null}</div><div className="agent-request-actions">{record.status==='complete'?<a className="secondary" href={'/api/agent/requests/'+record.id+'/bundle'}><Download size={15}/>Batch ZIP</a>:['failed','interrupted'].includes(record.status)?<button className="secondary" disabled={!!busy} onClick={()=>resume(record)}>Resume</button>:null}</div></article>)}

  </section>

  <section className="panel agent-history"><h2>Generated day history</h2><p className="helper">Generated files and external publication reports are separate records.</p>

   {!data.assets.length?<p className="agent-empty">Finished assets will appear here with their reading date and edition.</p>:<div className="agent-history-table">{data.assets.filter(a=>a.publicationAllowed).map(asset=>{const report=latestReport(asset);return <article key={asset.id}><div><strong>{asset.date}</strong><small>{asset.edition==='morning'?'6 AM · Morning':'6 PM · Evening'} · {asset.timezone}</small></div><div><span>{report?report.status+' · externally reported':'Generated · not reported scheduled'}</span><small>{report?`${report.platform} · ${report.postId}`:'Proposed: '+new Date(asset.proposedPublishAt).toLocaleString(undefined,{timeZone:asset.timezone})}</small></div><button className="secondary" onClick={()=>openReading(asset.readingId)} disabled={!!busy}>Open <ArrowUpRight size={15}/></button></article>;})}</div>}

   <p className="small-note agent-publication-note">Muse performs scheduling and posting through its own authorized Page access. Reports record returned platform IDs and times; this studio does not independently verify publication. Muse's connection and Page permissions are not established by local generation.</p>

  </section>

 </div>;

}
