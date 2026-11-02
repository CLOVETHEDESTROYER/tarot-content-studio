import { ArrowUpRight, Download, Search } from 'lucide-react';
import { useState } from 'react';

export function Library({readings, jobs, open, showExport}) {
  const [search, setSearch] = useState('');
  const items = readings.filter(d => `${d.title} ${d.reading_label||''} ${d.settings.date||''} ${d.settings.topic} ${d.cards.map(c => c.name).join(' ')}`.toLowerCase().includes(search.toLowerCase()));
  return <section className="library">
    <div className="library-toolbar"><p>Every reading, saved and ready for its next chapter.</p><label className="search"><Search size={17}/><input placeholder="Search your readings" aria-label="Search readings" value={search} onChange={e => setSearch(e.target.value)}/></label></div>
    {items.length ? <div className="library-table"><div className="library-columns"><span>Reading</span><span>Deck & format</span><span>Last saved</span><span>Actions</span></div>{items.map(d => {
      const exported = jobs.find(j => j.draft_id === d.id && j.kind === 'export' && j.status === 'done' && j.pipeline_version >= 2);
      return <article className="library-row" key={d.id}><button className="reading-link" onClick={() => open(d)}><img src={d.cards[0].image_url} alt=""/><span><strong>{d.title}</strong><small>{d.settings.topic}</small><small>{d.cards.map(c => c.name).join(' · ')}</small></span></button><div className="library-format">{d.reading_label||d.settings.deck.replaceAll('-',' ')}<small>{d.cards.length} card{d.cards.length > 1 ? 's' : ''} · {d.settings.duration}s</small></div><time dateTime={d.updated}>{new Date(d.updated).toLocaleDateString(undefined,{month:'short',day:'numeric'})}<small>{new Date(d.updated).toLocaleTimeString(undefined,{hour:'numeric',minute:'2-digit'})}</small></time><div className="library-actions">{exported ? <button className="icon-button" title="Download latest export" aria-label={`Download ${d.title}`} onClick={() => showExport(exported)}><Download size={18}/></button> : null}<button className="icon-button" title="Open reading" aria-label={`Open ${d.title}`} onClick={() => open(d)}><ArrowUpRight size={19}/></button></div></article>;
    })}</div> : <div className="empty-library"><h2>{search ? 'No matching readings.' : 'Your stories will live here.'}</h2><p>{search ? 'Try a different topic or card name.' : 'Create a reading to start your library.'}</p></div>}
  </section>;
}
