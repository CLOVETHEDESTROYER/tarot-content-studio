import {BackgroundPicker} from './BackgroundPicker';
import {VoiceDirection} from './VoiceDirection';
import { Shuffle, RotateCw } from 'lucide-react';
import {VoiceOptions} from './VoiceOptions';

export function Setup({settings, setSettings, config, draft, busy, onShuffle, onRedraw}) {
  const change = (key, value) => setSettings(s => ({...s, [key]: value}));
  return <section className="setup panel" aria-label="Reading setup">
    <h2>Reading setup</h2>
    <label className="topic">Topic<textarea aria-label="Topic" disabled={!!busy} maxLength={300} rows={2} value={settings.topic} onChange={e => change('topic', e.target.value)} /></label>
    <fieldset className="settings-fields" disabled={!!busy}>
      <label>Deck<select aria-label="Deck" value={settings.deck} onChange={e => change('deck', e.target.value)}>{config.decks.map(d => <option key={d.id} value={d.id} disabled={!d.ready}>{d.label}</option>)}</select></label>
      <label>Spread<select aria-label="Spread" value={settings.spread} onChange={e => change('spread', e.target.value)}><option value="one">One card</option><option value="three">Three cards</option></select></label>
      <label>Length<select aria-label="Length" value={settings.duration} onChange={e => change('duration', Number(e.target.value))}>{[30,45,60,90].map(n => <option key={n} value={n}>{n} seconds</option>)}</select></label>
      <label>Voice<select aria-label="Voice" value={settings.voice} onChange={e => change('voice', e.target.value)}>
        <VoiceOptions config={config}/>
      </select></label>
      <label>Writing<select aria-label="Writing" value={settings.writer} onChange={e => change('writer', e.target.value)}><option value="local">Built-in · free</option><option value="openai" disabled={!config.openai}>OpenAI · creative</option></select></label>
      <BackgroundPicker value={settings} change={change} config={config}/><VoiceDirection value={settings} change={change} config={config}/>
    </fieldset>
    <button className="primary shuffle" onClick={onShuffle} disabled={busy || !settings.topic.trim()}><Shuffle size={19}/>{busy === 'shuffle' ? 'Writing your reading…' : 'Shuffle & write'}</button>
    {(settings.deck !== draft?.settings.deck || settings.spread !== draft?.settings.spread) && draft ? <p className="helper">Shuffle to apply a new deck or spread.</p> : null}
    <div className="section-rule"/>
    <h2>Cards drawn</h2>
    {draft ? <div className="drawn-cards">{draft.cards.map((card, index) => <article className="drawn-card" key={card.id}>
      <img className={card.orientation === 'Reversed' ? 'reversed' : ''} src={card.image_url} alt={card.name}/>
      <div className="card-detail"><strong>{card.name}</strong><span className="position">{card.position}</span><div className="card-controls">
        <select aria-label={`${card.name} orientation`} value={card.orientation} disabled={!!busy || settings.deck !== draft.settings.deck || settings.spread !== draft.settings.spread} onChange={e => onRedraw(index, e.target.value)}><option>Upright</option><option>Reversed</option></select>
        <button className="icon-button" title={`Redraw ${card.name}`} aria-label={`Redraw ${card.name}`} disabled={!!busy || settings.deck !== draft.settings.deck || settings.spread !== draft.settings.spread} onClick={() => onRedraw(index)}><RotateCw size={17}/></button>
      </div></div>
    </article>)}</div> : <p className="helper">Your cards will appear here.</p>}
  </section>;
}
