import { RotateCw } from 'lucide-react';
import { clock } from './api';

export function ScriptEditor({draft, setDraft, manifest, busy, rewrite, dirty}) {
  const words = draft?.sections.reduce((n,s) => n + s.text.trim().split(/\s+/).filter(Boolean).length, 0) || 0;
  return <section className="script panel" aria-label="Script editor">
    <div className="script-heading"><div><h2>Your reading</h2><p className="helper">Edit before you export.</p></div><button title="Rewrite with these same cards" aria-label="Rewrite with these same cards" className="icon-button" disabled={!draft || !!busy} onClick={rewrite}><RotateCw size={17}/></button></div>
    {draft ? <>
      <label className="video-title">Video title<input aria-label="Video title" disabled={!!busy} maxLength={80} value={draft.title} onChange={e => setDraft({...draft, title:e.target.value})}/></label>
      <div className="script-sections">{draft.sections.map((section, index) => <label key={section.key}>
        <span>{section.label}{manifest && !dirty ? <small> {clock(manifest.sections[index].start)}–{clock(manifest.sections[index].end)}</small> : null}</span>
        <textarea aria-label={section.label} disabled={!!busy} maxLength={1000} rows={3} value={section.text} onChange={e => setDraft({...draft, sections:draft.sections.map((s,i) => i === index ? {...s,text:e.target.value} : s)})}/>
      </label>)}</div>
      <div className="script-meta"><span>{words} words</span><span>{draft.writing_source}</span></div>
      <div className="section-rule"/>
      <h2 className="export-heading">Export settings</h2><p className="helper">MP4 · 1080 × 1920 · 30 fps</p>
      <p className="small-note">Includes narration, burned-in captions, a cover, subtitles, and posting text.</p>
    </> : <p className="helper">Shuffle the deck to write your first reading.</p>}
  </section>;
}
