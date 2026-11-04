import { useEffect, useState, useRef } from 'react';
import { File, Folder, Upload, Settings, LoaderCircle, Check, X, Download, Sun, CalendarDays } from 'lucide-react';
import { api, defaults, defaultSettings, setToken } from './api';
import { Setup } from './Setup';
import { ScriptEditor } from './ScriptEditor';
import { Preview } from './Preview';
import { Library } from './Library';
import { ExportDialog } from './ExportDialog';
import {DailyStudio} from './DailyStudio';
import {DailySetup} from './DailySetup';
import {DailyPlanner} from './DailyPlanner';
import {AgentHistory} from './AgentHistory';
import {AppUpdates} from './AppUpdates';
import './daily.css';

export default function App() {
  const [config,setConfig] = useState(null), [draft,setDraft] = useState(null), [settings,setSettings] = useState(defaults);
  const [view,setView] = useState('editor'), [readings,setReadings] = useState([]), [jobs,setJobs] = useState([]);
  const [dirty,setDirty] = useState(false), [busy,setBusy] = useState(''), [job,setJob] = useState(null);
  const [manifest,setManifest] = useState(null), [previewKey,setPreviewKey] = useState(''), [output,setOutput] = useState(null);
  const [exportDialog,setExportDialog] = useState(null), [error,setError] = useState(''), [toast,setToast] = useState('');
  const [localInfo,setLocalInfo] = useState(false);
  const toastTimer = useRef(null), dirtyRef = useRef(false), mounted = useRef(false);
  const notify = text => {setToast(text);clearTimeout(toastTimer.current);toastTimer.current=setTimeout(()=>setToast(''),4500);};
  const refresh = async () => {const data=await api('/readings');setReadings(data.readings);setJobs(data.jobs);return data;};
  const clearPreview = () => {setManifest(null);setPreviewKey('');setOutput(null);setJob(null);};
  const open = async (reading, allJobs=jobs) => {
    setDraft(reading);setSettings(reading.settings);setDirty(false);setView('editor');setError('');clearPreview();
    const ready=allJobs.find(j=>j.draft_id===reading.id&&j.revision===reading.revision&&j.status==='done'&&j.pipeline_version>=2);
    if(ready) {
      try {const m=await api(`/previews/${ready.preview_key}/manifest`);setManifest(m);setPreviewKey(ready.preview_key);if(ready.kind==='export')setOutput(ready);} catch { /* A missing cache can be rebuilt from the saved reading. */ }
    }
  };
  useEffect(()=>{
    if(mounted.current)return;mounted.current=true;
    (async()=>{
      try {
        const conf=await api('/config');setToken(conf.token);setConfig(conf);setSettings(defaultSettings(conf));
        const data=await refresh();
        if(data.readings.length)await open(data.readings[0],data.jobs);
        else {const starter=await api('/readings','POST',{...defaultSettings(conf),writer:'local'});await open(starter,[]);await refresh();}
      } catch(e){setError(e.message);}
    })();
    return ()=>clearTimeout(toastTimer.current);
  },[]);
  useEffect(()=>{dirtyRef.current=dirty;},[dirty]);
  useEffect(()=>{
    const warn=e=>{if(dirtyRef.current){e.preventDefault();e.returnValue='';}};
    window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);
  },[]);
  useEffect(()=>{
    if(!job||!['queued','running'].includes(job.status))return;
    let stopped=false, timer;
    const poll=async()=>{
      try {
        const current=await api(`/jobs/${job.id}`);if(stopped)return;setJob(current);
        if(current.status==='done') {
          const m=await api(`/previews/${current.preview_key}/manifest`);if(stopped)return;
          setManifest(m);setPreviewKey(current.preview_key);setBusy('');
          if(current.kind==='export'){setOutput(current);setExportDialog(current);notify('Video exported. Your posting bundle is ready.');}
          else notify('Preview ready. Press Play to listen.');
          await refresh();
        } else if(current.status==='failed') {setBusy('');setError(current.error);await refresh();}
        else timer=setTimeout(poll,1000);
      } catch(e){if(!stopped){setError(e.message);setBusy('');}}
    };
    timer=setTimeout(poll,500);return()=>{stopped=true;clearTimeout(timer);};
  },[job?.id]);
  const editDraft=value=>{setDraft(value);setDirty(true);clearPreview();};
  const changeSettings=updater=>{setSettings(updater);setDirty(true);clearPreview();};
  const save=async(quiet=false,preserveSettings=false)=>{
    if(!draft)return null;
    const structural=settings.deck!==draft.settings.deck||settings.spread!==draft.settings.spread;
    const next=preserveSettings?draft.settings:{...settings,deck:draft.settings.deck,spread:draft.settings.spread};
    const result=await api(`/readings/${draft.id}`,'PUT',{revision:draft.revision,title:draft.title,sections:draft.sections,settings:next});
    setDraft(result);setDirty(structural);
    if(!quiet)notify(structural?'Script saved. Shuffle to apply the new deck or spread.':'Draft saved.');
    return result;
  };
  const act=async(name,work)=>{if(busy)return;setBusy(name);setError('');try{await work();}catch(e){setError(e.message);}finally{setBusy(current=>current===name?'':current);}};
  const shuffle=()=>act('shuffle',async()=>{
    if(draft&&dirty)await save(true,true);
    const next=await api('/readings','POST',settings);await open(next);await refresh();notify('New reading saved. Make it your own.');
  });
  const redraw= (index,orientation)=>act('redraw',async()=>{
    const current=await save(true);const next=await api(`/readings/${current.id}/redraw`,'POST',{revision:current.revision,index,...(orientation?{orientation}:{})});
    setDraft(next);setDirty(false);clearPreview();await refresh();notify('Card updated. The other script edits are preserved.');
  });
  const rewrite=()=>act('rewrite',async()=>{
    const current=await save(true);const next=await api(`/readings/${current.id}/rewrite`,'POST',{revision:current.revision});
    setDraft(next);setDirty(false);clearPreview();await refresh();notify('Script rewritten with the same cards.');
  });
  const start=kind=>act(kind,async()=>{
    if(settings.deck!==draft.settings.deck||settings.spread!==draft.settings.spread)throw new Error('Shuffle to apply your new deck or spread before previewing or exporting.');
    const current=await save(true);setOutput(null);
    const next=await api(`/readings/${current.id}/${kind}`,'POST',{revision:current.revision});setJob(next);
    setBusy('rendering');await refresh();
  });
  const goLibrary=()=>act('library',async()=>{if(draft&&dirty)await save(true);await refresh();setView('library');});
  const saveButton=()=>act('save',async()=>{await save();await refresh();});
  const goLive=()=>act('navigate',async()=>{if(draft&&dirty)await save(true);setView('live');});
  const goCards=()=>act('navigate',async()=>{if(draft&&dirty)await save(true);setView('cards');});
  const goUpdates=()=>act('navigate',async()=>{if(draft&&dirty)await save(true);setView('updates');});
  const goAgent=()=>act('navigate',async()=>{if(draft&&dirty)await save(true);setView('agent');});
  const goDaily=()=>act('navigate',async()=>{if(draft&&dirty)await save(true);setView('daily');});
  const goPlanner=()=>act('navigate',async()=>{if(draft&&dirty)await save(true);setView('planner');});
  const goTarot=()=>act('navigate',async()=>{if(draft&&dirty)await save(true);const data=await refresh();const previous=data.readings.find(d=>!d.settings.daily);if(previous)await open(previous,data.jobs);else{const starter=await api('/readings','POST',defaultSettings(config));await open(starter);await refresh();}});
  const createDaily=value=>act('daily-generate',async()=>{if(draft&&dirty)await save(true,true);const next=await api('/readings','POST',value);await open(next);await refresh();notify('Daily edition saved. Preview it, then export.');});
  const heading=view==='live'?'Live Studio':view==='cards'?'Card library & spreads':view==='updates'?'App Updates':view==='agent'?'History & Agent Jobs':view==='daily'?'Daily readings':view==='planner'?'Daily planner':view==='library'?'Your library':draft?.settings.daily?`${draft.settings.edition==='morning'?'Morning':'Evening'} ${draft.reading_label.toLowerCase()}`:'Create a reading';
  const subtitle=view==='live'?'Tarot, astrology and numerology for your live audience.':view==='cards'?'Explore every card, study its meaning, or use a longer spread.':view==='updates'?'Verified desktop releases, with your history kept safe.':view==='agent'?'Weekly readings, Muse handoffs, and a record for every day.':view==='daily'?'One shared reading, made for each day.':view==='planner'?'Morning at 6 AM. Evening at 6 PM. Denver time.':view==='library'?'A little inspiration, kept close.':draft?.settings.daily?'A collective edition with saved date, calculations, and sources.':'Turn a card pull into your next story.';
  return <div className="app-shell">
    <aside className="sidebar"><a className="brand" href="#" onClick={e=>{e.preventDefault();setView('editor');}}><img src="/assets/glyph-gold.png" alt=""/><span>StarPower</span><small>CONTENT STUDIO</small></a>
      <nav aria-label="Studio navigation"><button className={view==='live'?'active':''} onClick={goLive} disabled={!!busy}><Sun size={21}/>Live Studio</button><button className={view==='cards'?'active':''} onClick={goCards} disabled={!!busy}><File size={21}/>Card library & spreads</button><button className={view==='editor'&&!draft?.settings.daily?'active':''} onClick={goTarot} disabled={!!busy}><File size={21}/>Tarot studio</button><button className={view==='daily'||(view==='editor'&&draft?.settings.daily)?'active':''} onClick={goDaily} disabled={!!busy}><Sun size={21}/>Daily readings</button><button className={view==='planner'?'active':''} onClick={goPlanner} disabled={!!busy}><CalendarDays size={21}/>Daily planner</button><button className={view==='library'?'active':''} onClick={goLibrary} disabled={!!busy}><Folder size={21}/>Library</button><button className={view==='agent'?'active':''} onClick={goAgent} disabled={!!busy}><CalendarDays size={21}/>History & Agent Jobs</button><button className={view==='updates'?'active':''} onClick={goUpdates} disabled={!!busy}><Download size={21}/>App Updates</button></nav>
      <button className="local-studio" onClick={()=>setLocalInfo(!localInfo)}><Settings size={20}/>Local studio<span className="local-dot"/></button>
    </aside>
    <main><header className="app-header"><div><h1>{heading}</h1><p>{subtitle}</p></div><div className="header-actions">{view==='editor'?<><button className="secondary" onClick={saveButton} disabled={!draft||!!busy}>{busy==='save'?<LoaderCircle size={17} className="spin"/>:null}Save draft</button><button className="primary" disabled={!draft||!!busy} onClick={()=>start('export')}><Upload size={19}/>{busy==='rendering'&&job?.kind==='export'?'Exporting…':'Export video'}</button></>:<button className="primary" disabled={!!busy} onClick={view==='daily'?goPlanner:goDaily}>{view==='daily'?<CalendarDays size={18}/>:<Sun size={18}/>} {view==='daily'?'Daily planner':'Create a daily reading'}</button>}</div></header>
      {error?<div className="error-banner" role="alert"><span>{error}</span><button onClick={()=>setError('')} aria-label="Dismiss error"><X size={18}/></button></div>:null}
      {localInfo?<div className="local-info"><strong>Your own little production studio.</strong><p>Readings, audio, and exports stay on this computer. The local Windows/macOS voice and built-in writing are free. OpenAI options use your existing API connection.</p><p>Exports: <code>{config?.export_folder}</code></p><button className="text-button" onClick={()=>setLocalInfo(false)}>Got it</button></div>:null}
      {!config?<div className="loading"><LoaderCircle className="spin"/>Opening your studio…</div>:view==='live'||view==='cards'?<iframe title={view==='live'?'Live Studio':'Card library & spreads'} src={view==='live'?'/live':'/card-library'} style={{width:'100%',height:'calc(100vh - 120px)',border:0,display:'block'}}/>:view==='daily'?<DailyStudio config={config} onCreate={createDaily} busy={busy}/>:view==='updates'?<AppUpdates/>:view==='agent'?<AgentHistory config={config} open={open}/>:view==='planner'?<DailyPlanner config={config} open={open}/>:view==='library'?<Library readings={readings} jobs={jobs} open={open} showExport={setExportDialog}/>:<div className="workspace">
        {draft?.settings.daily?<DailySetup settings={settings} setSettings={changeSettings} config={config} draft={draft} busy={busy} onNew={goDaily} onRedraw={redraw}/>:<Setup settings={settings} setSettings={changeSettings} config={config} draft={draft} busy={busy} onShuffle={shuffle} onRedraw={redraw}/>}
        <div className="preview-column"><Preview draft={draft} manifest={manifest} previewKey={previewKey} output={output} busy={busy} dirty={dirty} onPrepare={()=>start('preview')} job={job}/>
          {output&&!dirty?<button className="secondary download-again" onClick={()=>setExportDialog(output)}><Download size={17}/>Download files</button>:null}
          {busy&&job&&['running','queued'].includes(job.status)?<p className="job-message" role="status">{job.message} · {job.progress}%</p>:null}
        </div>
        <ScriptEditor draft={draft} setDraft={editDraft} manifest={manifest} busy={busy} rewrite={rewrite} dirty={dirty}/>
      </div>}
    </main>
    {toast?<div className="toast" role="status"><Check size={17}/>{toast}</div>:null}
    {exportDialog?<ExportDialog job={exportDialog} close={()=>setExportDialog(null)}/>:null}
  </div>;
}
