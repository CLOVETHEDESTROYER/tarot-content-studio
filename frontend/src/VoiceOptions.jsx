export function VoiceOptions({config}) {
 return <>
  <option value="windows" disabled={!config.windows}>Windows voice · free</option>
  <option value="macos" disabled={!config.macos}>macOS voice · free</option>
  <option value="openai-coral" disabled={!config.openai}>OpenAI · Coral</option>
  <option value="openai-nova" disabled={!config.openai}>OpenAI · Nova</option>
  <option value="silent">Captions only</option>
 </>;
}
