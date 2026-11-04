export function VoiceOptions({config}) {
 return <>
  <option value="windows" disabled={!config.windows}>Windows voice · free</option>
  <option value="macos" disabled={!config.macos}>macOS voice · free</option>
  {(config.openai_voices||['marin','cedar','coral','nova','ash','ballad','sage','shimmer','verse','onyx','fable','alloy','echo']).map(voice=><option key={voice} value={'openai-'+voice} disabled={!config.openai}>OpenAI · {voice[0].toUpperCase()+voice.slice(1)}{['marin','cedar'].includes(voice)?' · recommended':''}</option>)}
  <option value="silent">Captions only</option>
 </>;
}
