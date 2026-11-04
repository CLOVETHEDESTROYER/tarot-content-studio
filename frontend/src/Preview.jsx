import { useEffect, useRef, useState } from 'react';
import { Play, Pause, Volume2, VolumeX, Maximize, LoaderCircle } from 'lucide-react';
import { clock } from './api';

export function Preview({background,draft, manifest, previewKey, output, busy, dirty, onPrepare, job}) {
  const audio = useRef(null), video = useRef(null), frame = useRef(null);
  const [playing, setPlaying] = useState(false), [time, setTime] = useState(0), [guides, setGuides] = useState(false), [muted, setMuted] = useState(false), [playError, setPlayError] = useState('');
  const duration = manifest?.duration || draft?.settings.duration || 45;
  useEffect(() => { setPlaying(false); setTime(0); setPlayError(''); }, [previewKey, draft?.id, dirty, output?.id]);
  useEffect(() => {
    if (!playing) return;
    let raf, last = 0;
    const tick = now => {
      if (now - last > 160) { setTime(audio.current?.currentTime || 0); last = now; }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);
  useEffect(() => { if (dirty) audio.current?.pause(); }, [dirty]);
  const toggle = async () => {
    if (!manifest || dirty) { onPrepare(); return; }
    if (playing) { audio.current.pause(); setPlaying(false); return; }
    try {
      if (audio.current.ended) audio.current.currentTime = 0;
      await audio.current.play(); setPlaying(true); setPlayError('');
    } catch { setPlayError('Playback was blocked. Press Play again.'); }
  };
  const seek = value => { if (audio.current && manifest) audio.current.currentTime = value; setTime(Number(value)); };
  const full = () => { const element = output ? video.current : frame.current; element?.requestFullscreen?.().catch(() => setPlayError('Fullscreen is unavailable in this browser.')); };
  let source = draft ? `/api/poster/${draft.id}?r=${draft.revision}&background=${encodeURIComponent(background||'solid')}` : null;
  if (manifest && !dirty) source = `/api/previews/${previewKey}/frame?t=${(Math.min(time, duration - .01)).toFixed(2)}`;
  return <section className="preview-area" aria-label="Video preview">
    <div className="preview-label">Video preview <span>(9:16)</span>{dirty ? <span className="unsaved">Unsaved changes</span> : null}</div>
    <div className="portrait" ref={frame}>
      {output && !dirty ? <video ref={video} controls playsInline preload="metadata" src={`/api/exports/${output.id}/reading.mp4`} poster={`/api/exports/${output.id}/cover.jpg`}/> : source ? <img src={source} alt="Portrait preview of your reading"/> : <div className="empty-preview"><span>✦</span><h3>Your next story<br/>starts with a card.</h3><p>Choose a reading to begin.</p></div>}
      {guides ? <div className="safe-guide"><span>Keep key text inside</span></div> : null}
      {busy && job && job.status !== 'done' ? <div className="render-overlay"><LoaderCircle className="spin" size={26}/><strong>{job.message}</strong><progress max={100} value={job.progress}/><span>{job.progress}%</span></div> : null}
    </div>
    {!output || dirty ? <div className="playback">
      <button className="play-button" onClick={toggle} disabled={!draft || !!busy} aria-label={!manifest || dirty ? 'Prepare preview' : playing ? 'Pause preview' : 'Play preview'}>{busy === 'preview' ? <LoaderCircle className="spin" size={19}/> : playing ? <Pause size={19} fill="currentColor"/> : <Play size={19} fill="currentColor"/>}</button>
      <span className="time">{clock(time)} / {clock(duration)}</span><input aria-label="Preview position" type="range" min="0" max={duration} step="0.1" value={time} disabled={!manifest || dirty} onChange={e => seek(e.target.value)}/>
      <button className="plain-icon" aria-label={muted ? 'Unmute narration' : 'Mute narration'} onClick={() => setMuted(!muted)}>{muted ? <VolumeX size={20}/> : <Volume2 size={20}/>}</button>
      <button className="plain-icon" aria-label="Fullscreen preview" onClick={full}><Maximize size={19}/></button>
    </div> : <p className="export-ready-note">Your finished MP4. Ready for TikTok and Facebook.</p>}
    <div className="preview-options"><label><input type="checkbox" checked={guides} onChange={e => setGuides(e.target.checked)}/> Safe guides (9:16)</label>{draft && !output ? <button className="text-button" onClick={onPrepare} disabled={!!busy}>{manifest && !dirty ? 'Rebuild preview' : 'Prepare preview'}</button> : null}</div>
    {!manifest && draft ? <p className="preview-hint">Prepare a preview to hear the voice and check timing.</p> : null}
    {playError ? <p className="inline-warning">{playError}</p> : null}
    {manifest?.warning ? <p className="inline-warning">{manifest.warning}</p> : null}
    {manifest && !output ? <p className="alignment-note">{manifest.alignment}</p> : null}
    {previewKey ? <audio ref={audio} src={`/api/previews/${previewKey}/audio`} preload="auto" muted={muted} onEnded={() => {setPlaying(false);setTime(duration - .01);}} onError={() => setPlayError('Audio could not load. Rebuild the preview and try again.')}/> : null}
  </section>;
}
