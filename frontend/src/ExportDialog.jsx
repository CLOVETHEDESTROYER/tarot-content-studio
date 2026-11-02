import { Download, X, Check } from 'lucide-react';
import { useEffect, useRef } from 'react';

export function ExportDialog({job, close}) {
  const dialog = useRef(null);
  useEffect(() => { dialog.current.showModal(); }, []);
  const link = (name) => `/api/exports/${job.id}/${name}?download=1`;
  return <dialog ref={dialog} className="export-dialog" onCancel={close} onClick={e => {if(e.target === dialog.current) close();}}><div className="dialog-content">
    <button className="dialog-close icon-button" aria-label="Close export downloads" onClick={close}><X size={20}/></button>
    <div className="success-mark"><Check size={24}/></div><h2>Your reading is ready.</h2><p>A story made. A little perspective to share.</p>
    <video controls playsInline preload="metadata" src={`/api/exports/${job.id}/reading.mp4`} poster={`/api/exports/${job.id}/cover.jpg`}/>
    <p className="export-spec">1080 × 1920 · 30 fps · {job.duration}s · Revision {job.revision}</p>
    <a className="primary download-main" href={link('reading.mp4')}><Download size={18}/> Download MP4</a>
    <a className="secondary download-main" href={link('posting-bundle.zip')}>Download posting bundle</a>
    <div className="extra-downloads"><a href={link('cover.jpg')}>Cover image</a><a href={link('subtitles.srt')}>Subtitles</a><a href={link('caption.txt')}>Posting text</a>{job.files?.includes('sources.txt')?<a href={link('sources.txt')}>Date & sources</a>:null}</div>
    <p className="small-note">The posting bundle includes the video, cover, subtitles, caption text, and saved reading. Upload the MP4 in TikTok or Facebook.</p>
  </div></dialog>;
}
