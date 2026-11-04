const $ = id => document.getElementById(id);

const audio = $('broadcast-audio');

const scene = document.querySelector('.broadcast-scene');

const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

let displayId = '', revision = 0, state = null, clockOffset = 0;

let captionParts = [], captionStart = 0, captionDuration = 90000;

let currentShowcase = null;

let connectionError = '';

let audioRetries = 0;

const broadcastTicket = new URLSearchParams(location.search).get('ticket');

const broadcastAccess = (async () => {

  if (broadcastTicket) return;

  const key = new URLSearchParams(location.hash.slice(1)).get('key');

  if (!key) return;

  const response = await fetch('/api/live/overlay-access', {

    method: 'POST', headers: {Authorization: 'Bearer ' + key}, credentials: 'same-origin',

  });

  if (!response.ok) throw new Error('Broadcast link expired. Open a fresh link from Live Studio.');

})();

broadcastAccess.catch(() => {});

function fitViewerText() {

  const panel = document.querySelector('.broadcast-viewer');

  const name = $('broadcast-viewer'), question = $('broadcast-question');

  name.style.fontSize = '34px'; question.style.fontSize = '25px';

  for (let size = 33; size >= 18 && panel.scrollHeight > panel.clientHeight; size--) {

    name.style.fontSize = Math.max(24, size) + 'px';

    question.style.fontSize = Math.min(25, size) + 'px';

  }

}

function setCaption(value) {

  if ($('broadcast-caption').textContent === value) return;

  $('broadcast-caption').textContent = value;

  const panel = document.querySelector('.broadcast-caption');

  panel.classList.remove('caption-enter');

  void panel.offsetWidth;

  panel.classList.add('caption-enter');

}

function fitScene() {

  const scale = Math.min(innerWidth / 1080, innerHeight / 1920);

  document.querySelector('.broadcast-scene').style.transform = `translateX(-50%) scale(${scale})`;

}

addEventListener('resize', fitScene); fitScene();

function text(tag, value, className) {

  const el = document.createElement(tag); el.textContent = value;

  if (className) el.className = className;

  return el;

}

function chunks(reading) {

  const words = reading.split(/\s+/).flatMap(word => word.match(/.{1,140}/g) || []); const parts = []; let part = '';

  for (const word of words) {

    if ((part + ' ' + word).length > 140 && part) { parts.push(part); part = ''; }

    part += (part ? ' ' : '') + word;

  }

  if (part) parts.push(part);

  return parts;

}

async function playNarration() {

  if (!audio.src) return;

  try { await audio.play(); $('enable-audio').hidden = true; }

  catch { $('enable-audio').hidden = false; }

}

$('enable-audio').addEventListener('click', async () => {

  if (!audio.src) {

    $('enable-audio').textContent = 'Narration starts after the cards';

    return;

  }

  if (audio.ended) audio.currentTime = 0;

  await playNarration();

});

audio.addEventListener('ended', () => {

  $('enable-audio').textContent = 'Replay narration';

  $('enable-audio').hidden = false;

});

audio.addEventListener('error', () => {

  $('enable-audio').textContent = 'Retry narration';

  $('enable-audio').hidden = false;

  const source = audio.getAttribute('src');

  if (source && state?.running && audioRetries++ < 3) {

    setTimeout(() => {

      if (audio.getAttribute('src') !== source || !state?.running) return;

      audio.load();

      playNarration();

    }, 5000);

  }

});

async function showReading(display) {

  const token = ++revision;

  currentShowcase?.remove();

  currentShowcase = null;

  displayId = display.id;

  scene.dataset.readingType=display.reading_type||'tarot';

  $('broadcast-status').textContent=(display.reading_label||'Tarot')+(display.reading_date?' · '+display.reading_date:'');

  $('broadcast-cards').classList.toggle('many-cards',display.cards.length>3);

  audioRetries = 0;

  audio.pause(); audio.removeAttribute('src'); audio.load();

  $('broadcast-viewer').textContent = '@' + display.viewer;

  $('broadcast-question').textContent = display.question.length > 180 ? display.question.slice(0,177) + '...' : display.question;

  $('broadcast-cards').replaceChildren();

  $('broadcast-cards').dataset.count = display.cards.length;

  scene.dataset.phase = 'dealing';

  fitViewerText();

  setCaption('Your cards are being revealed...');

  captionParts = [];

  for (const card of display.cards) {

    if (token !== revision) return;

    const article = document.createElement('article'); article.className = 'broadcast-card';

    article.innerHTML = '<div class="broadcast-frame"><div class="broadcast-flip"><div class="broadcast-back"><img src="/static/brand/glyph-gold.png" alt=""></div><div class="broadcast-face"><img alt=""></div></div></div>';

    const image = article.querySelector('.broadcast-face img'); image.src = card.image_url; image.alt = card.name;

    if (card.orientation === 'Reversed') image.className = 'reversed';

    article.classList.add('awaiting-placement');

    article.prepend(text('p',card.position)); article.append(text('h3',card.name),text('small',card.orientation));

    $('broadcast-cards').append(article);

    await Promise.race([image.decode().catch(() => {}), sleep(5000)]);

    if (token !== revision) return;

    const showcase = document.createElement('section');

    showcase.className = 'card-showcase';

    showcase.setAttribute('aria-label', card.name + ', ' + card.orientation);

    showcase.append(text('p', '@' + display.viewer + ' / ' + card.position, 'showcase-heading'));

    const frame = article.querySelector('.broadcast-frame').cloneNode(true);

    showcase.append(frame);

    const label = document.createElement('div'); label.className = 'showcase-caption';

    label.append(text('h2', card.name), text('p', card.orientation)); showcase.append(label);

    if (!image.naturalWidth) {

      const face = frame.querySelector('.broadcast-face');

      face.classList.add('image-missing'); face.replaceChildren(text('span', card.name));

    }

    currentShowcase = showcase; scene.append(showcase);

    await sleep(100);

    if (token !== revision) return;

    showcase.classList.add('revealed');

    // Hold the face for two full seconds after the flip has completed.

    await sleep(reducedMotion ? 1 : 850);

    if (token !== revision) return;

    await sleep(2000);

    if (token !== revision) return;

    showcase.classList.add('landing');

    const source = frame.getBoundingClientRect();

    const target = article.querySelector('.broadcast-frame').getBoundingClientRect();

    const scale = scene.getBoundingClientRect().width / 1080;

    const landing = frame.animate([

      {transform: 'translate(0, 0) scale(1)'},

      {transform: `translate(${(target.left-source.left)/scale}px, ${(target.top-source.top)/scale}px) scale(${target.width/source.width})`},

    ], {duration: reducedMotion ? 1 : 750, easing: 'cubic-bezier(.25,.75,.25,1)', fill: 'forwards'});

    await landing.finished.catch(() => {});

    if (token !== revision) return;

    article.classList.add('revealed');

    article.classList.remove('awaiting-placement');

    showcase.remove(); currentShowcase = null;

    await sleep(350);

  }

  if (token !== revision) return;

  scene.dataset.phase = 'reading';

  fitViewerText();

  captionParts = chunks(display.reading); captionStart = Date.now();

  captionDuration = Math.max(20000, Math.min(90000, ((state?.settings.interval || 270) - 18) * 1000));

  setCaption(captionParts[0] || 'Take a moment to reflect on your cards.');

  if (display.has_audio) {

    audio.src = '/api/live/audio/' + encodeURIComponent(display.id) +

      (broadcastTicket ? '?ticket=' + encodeURIComponent(broadcastTicket) : '');

    $('enable-audio').textContent = 'Play narration';

    if (state?.running) await playNarration();

    else $('enable-audio').hidden = false;

  } else {

    $('enable-audio').textContent = 'No narration for this reading';

    $('enable-audio').hidden = false;

  }

}

function updateTicker() {

  if (!state) return;

  const remaining = Math.max(0, Math.ceil(state.next_at - (Date.now()/1000 + clockOffset)));

  $('broadcast-status').textContent = !state.running ? 'Between live sessions' : state.paused ? 'A moment to pause' : state.processing ? 'The next reading is on its way' : state.display ? (state.display.reading_label||'Tarot')+' · '+(state.display.reading_date||'') : 'Your moment of clarity';

  if (connectionError) $('broadcast-status').textContent = connectionError;

  $('broadcast-next').textContent = state.running && !state.paused && remaining > 0 ? `Next pull in ${Math.floor(remaining/60)}:${String(remaining%60).padStart(2,'0')}` : `Readings every ${state.settings.interval/60} minutes`;

  $('broadcast-queue').textContent = state.queue.length ? 'Up next: ' + state.queue.slice(0,3).map(q=>'@'+(q.viewer.length > 24 ? q.viewer.slice(0,21)+'...' : q.viewer)).join('  /  ') : 'Bring a question. Stay for a little perspective.';

  if (captionParts.length) {

    const progress = audio.src && Number.isFinite(audio.duration) && audio.duration > 0 ? audio.currentTime / audio.duration : (Date.now()-captionStart)/captionDuration;

    const index = Math.min(captionParts.length-1, Math.floor(progress*captionParts.length));

    setCaption(captionParts[Math.max(0,index)]);

    if (progress >= 1 || audio.ended) scene.dataset.phase = 'holding';

  }

}

async function poll() {

  try {

    await broadcastAccess;

    const response = await fetch('/api/live/state?public=1', {

      cache:'no-store', headers: broadcastTicket ? {'X-Broadcast-Ticket': broadcastTicket} : {},

    });

    if (response.status === 401) {

      connectionError = 'Access missing or expired. Copy the complete private broadcast link.';

      $('broadcast-status').textContent = connectionError;

      return;

    }

    if (!response.ok) throw new Error('Server unavailable');

    connectionError = '';

    const wasRunning = state?.running;

    state = await response.json(); clockOffset = state.server_now - Date.now()/1000;

    if (wasRunning && !state.running) audio.pause();

    $('broadcast-presenter').textContent = state.settings.presenter + ' presents';

    if (state.display && state.display.id !== displayId) {

      showReading(state.display).catch(() => {

        currentShowcase?.remove(); currentShowcase = null;

        scene.dataset.phase = 'holding';

        setCaption('The reading could not be displayed. Please check the host dashboard.');

      });

    }

    updateTicker();

  } catch {

    connectionError = 'Connection interrupted. Reconnecting to the reading room...';

    $('broadcast-status').textContent = connectionError;

  }

}

poll(); setInterval(poll,2000); setInterval(updateTicker,500);
