import {useEffect,useState} from 'react';
import {Download,RefreshCw,RotateCcw,ShieldCheck} from 'lucide-react';

export function AppUpdates() {
 const [state,setState]=useState(null),[error,setError]=useState(''),[token,setToken]=useState(''),[working,setWorking]=useState(false);
 const bridge=()=>window.pywebview?.api;
 useEffect(()=>{let active=true;const refresh=async()=>{if(bridge()){try{const value=await bridge().update_state();if(active)setState(value);}catch(e){if(active)setError(e.message);}}};refresh();const timer=setInterval(refresh,1000);return()=>{active=false;clearInterval(timer);};},[]);
 const act=async(name,...args)=>{setWorking(true);setError('');try{setState(await bridge()[name](...args));}catch(e){setError(e.message||'The update could not complete.');}finally{setWorking(false);if(name==='save_update_token')setToken('');}};
 if(!state)return <section className="panel" style={{margin:28,maxWidth:760}}><h2>Desktop updates</h2><p className="helper" style={{marginTop:16}}>Open the packaged StarPower desktop application to check and install updates. The browser development studio keeps using Git and the setup scripts.</p></section>;
 const busy=working||['checking','downloading','waiting','installing'].includes(state.status);
 return <div style={{padding:28,maxWidth:1050,margin:'auto'}}><section className="panel"><ShieldCheck size={29} color="#446e50"/><h2 style={{margin:'18px 0 10px'}}>Keep your studio up to date.</h2><p className="helper">Installed version {state.current}. Updates preserve your readings, exports, selected Google Drive exchange, and Muse request history.</p>
  <p role="status" style={{margin:'24px 0 14px',lineHeight:1.7}}>{state.message}</p>{error?<p className="daily-error" role="alert">{error}</p>:null}
  {state.status==='downloading'?<progress value={state.progress} max="100" style={{width:'100%'}}/>:null}
  <div className="agent-buttons"><button className="secondary" disabled={busy} onClick={()=>act('check_update')}><RefreshCw size={16}/>Check for Updates</button>
   {state.available&&state.status!=='prepared'&&!['waiting','installing'].includes(state.status)?<button className="primary" disabled={busy} onClick={()=>act('download_update')}><Download size={16}/>Download {state.available.version}</button>:null}
   {state.status==='prepared'?<button className="primary" disabled={working} onClick={()=>act('install_update')}>Install & Relaunch</button>:null}
   {['downloading','waiting'].includes(state.status)?<button className="secondary" onClick={()=>act('cancel_update')}>Cancel {state.status==='waiting'?'waiting':'download'}</button>:null}
  </div>
  {state.available?.notes?<div style={{whiteSpace:'pre-wrap',fontSize:13,lineHeight:1.7,margin:'20px 0'}}>{state.available.notes}</div>:null}
  <p className="small-note">Installation waits for active batches and exports to finish. The previous app and a history snapshot are retained; automatic rollback changes the app only.</p>
 </section><section className="panel" style={{marginTop:24}}><h2>Private release access</h2><p className="helper" style={{margin:'12px 0 20px'}}>Your repository stays private. An existing GitHub CLI sign-in is used when available. Otherwise, save a token with read-only Contents access to this repository in the system credential store.</p>
  <label>GitHub repository token<input type="password" aria-label="GitHub update access token" autoComplete="off" value={token} onChange={e=>setToken(e.target.value)}/></label><button className="secondary" style={{marginTop:15}} disabled={busy||!token} onClick={()=>act('save_update_token',token)}>Save update access</button>
  <p className="small-note" style={{marginTop:12}}>The token is never bundled, returned to the interface, or written to your exchange files.</p>
 </section><section className="panel" style={{marginTop:24}}><h2>Recovery</h2><p className="helper" style={{margin:'12px 0'}}>Recovery files: <span style={{overflowWrap:'anywhere'}}>{state.recoveryFolder}</span></p><button className="secondary" disabled={busy} onClick={()=>act('restore_previous')}><RotateCcw size={16}/>Restore Previous App & Relaunch</button><p className="small-note" style={{marginTop:14}}>Current history is kept. Recovery never restores an older database over your latest readings or publication records.</p></section></div>;
}
