import './backgrounds.css';

export function BackgroundPicker({value,change,config}) {
 const choices=config.backgrounds||[];
 return <fieldset className="background-picker"><legend>Reading background</legend>
  <div className="background-choices">{choices.map(bg=><button type="button" key={bg.id}
   className={'background-choice'+((value.background||'solid')===bg.id?' selected':'')}
   aria-label={'Background: '+bg.label} aria-pressed={(value.background||'solid')===bg.id}
   onClick={()=>change('background',bg.id)}>
   <img src={bg.thumbnail} alt="" loading="lazy"/><span>{bg.label}</span>
  </button>)}</div>
  <p className="small-note">Artwork sits behind your cards and captions. Your chosen background is saved with the reading.</p>
 </fieldset>;
}
