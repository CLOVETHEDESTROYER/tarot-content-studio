const $ = (id) => document.getElementById(id);
let state;
let initialized = false;
let queueSignature = '';
let displayId = '';
let clockOffset = 0;

function notice(text) { $('notice').textContent = text; $('notice').hidden = false; }
async function action(name, data = {}) {
  const response = await fetch(`/api/live/${name}`, {method:'POST', headers:{'Content-Type':'application/json', 'X-Live-CSRF':document.querySelector('meta[name="live-csrf"]').content}, body:JSON.stringify(data)});
  if (response.status === 401) { location.assign('/live/login'); throw new Error('Please sign in again.'); }
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Action failed.');
  await refresh();
}
function bind(id, callback) {
  $(id).addEventListener('click', async () => {
    $(id).disabled = true;
    try { await callback(); } catch (e) { notice(e.message); }
    finally { $(id).disabled = false; if (state) renderStatus(); }
  });
}
function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function renderStatus() {
  $('session-status').textContent = state.running ? (state.paused ? 'Session paused' : 'Session running') : 'Session offline';
  document.querySelector('.broadcast-link').href = state.overlay_url;
  $('start').disabled = state.running;
  $('pause').disabled = !state.running;
  $('end').disabled = !state.running;
  $('pause').textContent = state.paused ? 'Resume' : 'Pause';
  $('worker-error').hidden = !state.last_error;
  $('worker-error').textContent = state.last_error;
  $('queue-count').textContent = state.queue.length;
  $('chat-status').textContent = `${state.chat.message} | ${state.chat.accepted} requests accepted`;
  $('connect').disabled = state.chat.connected || !state.running;
  $('disconnect').disabled = state.chat.message === 'Not connected' || state.chat.message === 'Disconnected';
  $('carry').textContent = state.carry ? `@${state.carry.viewer}: ${state.carry.question}${state.carry.status === 'pending' ? ' (approval needed)' : ''}` : 'None saved. Ending the session will keep the newest waiting request, or the current request if nobody is waiting.';
  const signature = JSON.stringify(state.queue);
  if (signature !== queueSignature) {
    queueSignature = signature;
    $('queue').replaceChildren();
    if (!state.queue.length) $('queue').append(element('li', 'No requests waiting.', 'queue-empty'));
    for (const item of state.queue) {
      const row = element('li');
      const copy = element('div');
      copy.append(element('strong', '@' + item.viewer), element('p', item.question), element('small', (item.reading_type||'tarot')+' · '+(item.status === 'pending' ? 'Needs approval' : 'Ready')));
      const controls = element('div', undefined, 'button-row');
      if (item.status === 'pending') {
        const approve = element('button', 'Approve');
        approve.addEventListener('click', () => action('approve', {id:item.id}).catch(e => notice(e.message)));
        controls.append(approve);
      }
      const remove = element('button', 'Remove', 'secondary');
      remove.addEventListener('click', () => action('remove', {id:item.id}).catch(e => notice(e.message)));
      controls.append(remove);
      row.append(copy, controls);
      $('queue').append(row);
    }
  }
  if (state.display && state.display.id !== displayId) {
    displayId = state.display.id;
    const display = state.display;
    $('current-reading').replaceChildren(element('h3', '@' + display.viewer+' · '+(display.reading_label||'Tarot')), element('p', display.question));
    const cards = element('div', undefined, 'host-cards');
    for (const card of display.cards) {
      const image = element('img'); image.src = card.image_url; image.alt = card.name + ', ' + card.orientation;
      if (card.orientation === 'Reversed') image.className = 'reversed';
      cards.append(image);
    }
    $('current-reading').append(cards, element('p', display.reading, 'host-transcript'));
  }
  renderClock();
}
function renderClock() {
  if (!state) return;
  let text = 'Start live to begin';
  if (state.running) {
    const remaining = Math.max(0, Math.ceil(state.next_at - (Date.now()/1000 + clockOffset)));
    if (state.processing) text = 'Preparing reading...';
    else if (state.paused) text = 'Paused';
    else if (remaining > 0) text = `Next pull in ${Math.floor(remaining/60)}:${String(remaining%60).padStart(2,'0')}`;
    else if (state.queue[0]?.status === 'pending') text = 'Approve the first request';
    else text = state.queue.length ? 'Next pull ready' : 'Waiting for requests';
  }
  $('countdown').textContent = text;
}
async function refresh() {
  const response = await fetch('/api/live/state', {cache:'no-store'});
  if (response.status === 401) { location.assign('/live/login'); return; }
  if (!response.ok) throw new Error('Live Studio unavailable. Keep this page on the streaming computer.');
  state = await response.json();
  clockOffset = state.server_now - Date.now()/1000;
  if (!initialized) {
    const s = state.settings;
    $('interval').value = String(s.interval); $('approval').checked = s.approval;
    $('live-ai').checked = s.use_ai; $('live-voice').checked = s.use_voice;
    $('live-spread').value = s.spread; $('presenter').value = s.presenter;
    $('live-type').value=s.reading_type||'tarot';$('live-date').value=s.reading_date||'';$('live-background').value=s.background||'solid';$('live-background-preview').src='/api/backgrounds/'+(s.background||'solid')+'?thumbnail=1';$('live-style').value=s.style||'esoteric-minimal';$('live-narrator').value=s.voice||'openai-coral';$('live-delivery').value=s.voice_style||'engaging';$('live-energy').value=s.voice_energy||'expressive';
    $('live-deck').value = s.deck || 'celebrity';
    if (state.chat.handle) $('handle').value = state.chat.handle;
    initialized = true;
  }
  renderStatus();
}
function saveSettings() {
  return action('settings', {interval:Number($('interval').value), approval:$('approval').checked,
    use_ai:$('live-ai').checked, use_voice:$('live-voice').checked,
    spread:$('live-spread').value, presenter:$('presenter').value, deck:$('live-deck').value,reading_type:$('live-type').value,reading_date:$('live-date').value,style:$('live-style').value,background:$('live-background').value,voice:$('live-narrator').value,voice_style:$('live-delivery').value,voice_energy:$('live-energy').value,timezone:'America/Denver'});
}
bind('start', async () => { await saveSettings(); await action('start'); });
bind('pause', () => action('pause'));
bind('end', async () => {
  if (confirm('End this session? Keep only the newest waiting request (or current request if nobody is waiting), and erase all other queued requests?')) await action('end');
});
bind('disconnect', () => action('disconnect'));
bind('rotate-overlay', async () => {
  if (confirm('Reset the broadcast link? Existing broadcast windows will lose access. Update the link in TikTok after resetting it.')) await action('rotate-overlay');
});
bind('demo', async () => {
  const response = await fetch('/static/live-demo-requests.json', {cache:'no-store'});
  if (!response.ok) throw new Error('Could not load example requests. Please try again.');
  const requests = await response.json();
  const waiting = new Set((state?.queue || []).map(item => item.viewer.toLowerCase()));
  const active = state?.processing?.request?.viewer;
  if (active) waiting.add(active.toLowerCase());
  let added = 0;
  for (const [viewer, question] of requests) {
    if (waiting.has(viewer.toLowerCase())) continue;
    await action('request', {viewer, question});
    added++;
  }
  notice(`${added} detailed example requests added. Approve them if approval is enabled. Readings follow the selected interval.`);
});
for (const [id, callback] of [
  ['settings-form', async () => { await saveSettings(); notice('Settings saved.'); }],
  ['chat-form', () => action('connect', {handle:$('handle').value})],
  ['request-form', async () => { await action('request', {viewer:$('viewer').value, question:$('live-question').value,reading_type:$('request-type').value||null}); $('request-form').reset(); }],
]) $(id).addEventListener('submit', async event => { event.preventDefault(); try { await callback(); } catch (e) { notice(e.message); } });
refresh().catch(e => notice(e.message));
setInterval(() => refresh().catch(e => notice(e.message)), 2000);
setInterval(renderClock, 1000);

bind('voice-sample',async()=>{
 const config=await(await fetch('/api/config')).json();const response=await fetch('/api/voice/sample',{method:'POST',headers:{'Content-Type':'application/json','X-Studio-Token':config.token},body:JSON.stringify({voice:$('live-narrator').value,voice_style:$('live-delivery').value,voice_energy:$('live-energy').value})});
 const result=await response.json();if(!response.ok)throw Error(result.error);const audio=$('voice-sample-audio');audio.hidden=false;audio.src=result.url;audio.play().catch(()=>notice('Sample ready. Press Play to listen.'));
});

$('live-background').addEventListener('change',()=>{$('live-background-preview').src='/api/backgrounds/'+$('live-background').value+'?thumbnail=1';});
