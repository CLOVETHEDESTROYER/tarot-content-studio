// Card library shares the desktop engine's local mutation protection.
const studioFetch=window.fetch.bind(window);
let studioAccess;
window.fetch=async (input,options={})=>{
 if(typeof input==='string' && input.startsWith('/api/') && options.method && options.method.toUpperCase()!=='GET'){
  studioAccess=studioAccess||studioFetch('/api/config').then(r=>r.json());
  options={...options,headers:{...options.headers,'X-Studio-Token':(await studioAccess).token}};
 }
 return studioFetch(input,options);
};
const dealButton = document.querySelector("#deal");
const browseDeckButton = document.querySelector("#browse-deck");
const mobileDealButton = document.querySelector("#mobile-deal");
const mobileDeckButton = document.querySelector("#mobile-deck");
const cardsEl = document.querySelector("#cards");
const cardListEl = document.querySelector("#card-list");
const readingText = document.querySelector("#reading-text");
const spreadLabel = document.querySelector("#spread-label");
const sourceLabel = document.querySelector("#source-label");
const seedEl = document.querySelector("#seed");
const audio = document.querySelector("#audio");
const panelTitle = document.querySelector("#panel-title");
const readingTab = document.querySelector("#reading-tab");
const deckTab = document.querySelector("#deck-tab");
const deckLibrary = document.querySelector("#deck-library");
const deckGrid = document.querySelector("#deck-grid");
const deckGroup = document.querySelector("#deck-group");
const deckSearch = document.querySelector("#deck-search");
const cardDialog = document.querySelector("#card-dialog");
const closeCardButton = document.querySelector("#close-card");
const speakCardButton = document.querySelector("#speak-card");
const cardAudio = document.querySelector("#card-audio");
const deckSelect = document.querySelector('#deck-select');

let deck = [];
let selectedCard = null;

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const isMobileViewport = () => window.matchMedia("(max-width: 760px)").matches;

function cardNode(card, index, total) {
  const el = document.createElement("article");
  el.className = `tarot-card is-dealing ${card.orientation === "Reversed" ? "is-reversed" : ""}`;
  el.style.setProperty("--delay", `${index * 90}ms`);
  el.innerHTML = `
    <div class="card-position">${card.position}</div>
    <div class="card-frame">
      <div class="card-flipper">
        <div class="card-side card-back" aria-hidden="true">
          <span><img src="/static/brand/glyph-gold.png" alt="" width="64" height="64"></span>
        </div>
        <div class="card-side card-face">
          <img src="${card.image_url}" alt="${card.name}">
        </div>
      </div>
    </div>
    <div class="card-caption">
      <strong>${card.name}</strong>
      <span>${card.orientation}</span>
    </div>
  `;
  if (total >= 8) el.classList.add("compact");
  return el;
}

function meaningNode(card) {
  const el = document.createElement("section");
  el.className = "meaning";
  const celeb = card.celebrity ? `<span>${card.celebrity}</span>` : "";
  el.innerHTML = `
    <div>
      <h3>${card.position}</h3>
      <p>${card.name} &middot; ${card.orientation}</p>
      ${celeb}
    </div>
    <p>${card.meaning}</p>
  `;
  return el;
}

function setLoading(isLoading) {
  deckSelect.disabled = isLoading;
  dealButton.disabled = isLoading;
  mobileDealButton.disabled = isLoading;
  dealButton.querySelector("span").textContent = isLoading ? "Reading..." : "Deal";
  mobileDealButton.querySelector("span").textContent = isLoading ? "Reading..." : "Deal";
  sourceLabel.textContent = isLoading ? "Shuffling" : sourceLabel.textContent;
}

function setPanel(view) {
  const isDeck = view === "deck";
  document.body.classList.toggle("deck-open", isDeck);
  panelTitle.textContent = isDeck ? "Deck Library" : "Cards Pulled";
  readingTab.classList.toggle("active", !isDeck);
  deckTab.classList.toggle("active", isDeck);
  cardListEl.hidden = isDeck;
  deckLibrary.hidden = !isDeck;
  seedEl.textContent = isDeck ? `${deck.length || 78} cards` : seedEl.textContent;
  if (isDeck) loadDeck();
}

async function revealCards(cards) {
  cardsEl.className = `cards count-${cards.length}`;
  for (const [index, card] of cards.entries()) {
    const node = cardNode(card, index, cards.length);
    cardsEl.appendChild(node);
    sourceLabel.textContent = `Pulling ${index + 1} of ${cards.length}`;
    await sleep(520);
    node.classList.add("is-revealed");
    await sleep(760);
    cardListEl.appendChild(meaningNode(card));
    await sleep(260);
  }
}

async function deal() {
  setPanel("reading");
  setLoading(true);
  audio.hidden = true;
  audio.removeAttribute("src");
  readingText.textContent = "The deck is being shuffled. Watch each card land, pause, and turn over.";
  cardsEl.className = "cards";
  cardsEl.innerHTML = "";
  cardListEl.innerHTML = "";
  if (isMobileViewport()) {
    document.querySelector(".table-stage").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const payload = {
    question: document.querySelector("#question").value,
    spread: document.querySelector("#spread").value,
    deck: deckSelect.value,
    use_ai: document.querySelector("#use-ai").checked,
    use_voice: document.querySelector("#use-voice").checked,
  };

  try {
    const response = await fetch("/api/deal", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`Deal failed: ${response.status}`);
    const result = await response.json();

    spreadLabel.textContent = result.spread;
    seedEl.textContent = result.seed;
    await revealCards(result.cards);

    readingText.textContent = result.reading;
    sourceLabel.textContent = result.reading_source === "openai" ? "AI Reading" : "Local Reading";

    if (result.audio_url) {
      audio.src = result.audio_url;
      audio.hidden = false;
      audio.play().catch(() => {});
    }
  } catch (error) {
    readingText.textContent = "The reading failed before the cards could speak. Check the terminal for the stack trace and try again.";
    sourceLabel.textContent = "Error";
  } finally {
    setLoading(false);
  }
}

function groupLabel(card, mode) {
  if (mode === "suit") return card.suit || "Major Arcana";
  if (mode === "arcana") return card.arcana;
  return "Full Deck";
}

function renderDeck() {
  const mode = deckGroup.value;
  const query = deckSearch.value.trim().toLowerCase();
  const filtered = deck.filter((card) => {
    const text = [card.name, card.arcana, card.suit, card.celebrity].filter(Boolean).join(" ").toLowerCase();
    return !query || text.includes(query);
  });
  const groups = new Map();
  for (const card of filtered) {
    const label = groupLabel(card, mode);
    if (!groups.has(label)) groups.set(label, []);
    groups.get(label).push(card);
  }

  deckGrid.innerHTML = "";
  if (!filtered.length) {
    deckGrid.innerHTML = `<p class="empty-state">No cards match that search.</p>`;
    return;
  }

  let renderedCards = 0;
  for (const [label, cards] of groups) {
    const section = document.createElement("section");
    section.className = "deck-group";
    section.innerHTML = `<h3>${label}</h3>`;
    const list = document.createElement("div");
    list.className = "deck-card-grid";
    for (const card of cards) {
      const imageLoading = renderedCards < 6 ? "eager" : "lazy";
      const button = document.createElement("button");
      button.className = "deck-card";
      button.type = "button";
      button.innerHTML = `
        <img src="${card.image_url}" alt="${card.name}" loading="${imageLoading}" decoding="async">
        <span>${card.name}</span>
        <small>${card.celebrity || card.suit || card.arcana}</small>
      `;
      button.addEventListener("click", () => openCard(card));
      list.appendChild(button);
      renderedCards += 1;
    }
    section.appendChild(list);
    deckGrid.appendChild(section);
  }
}

async function loadDeck() {
  if (deck.length) {
    renderDeck();
    return;
  }
  deckGrid.innerHTML = `<p class="empty-state">Opening the deck library...</p>`;
  const key = deckSelect.value;
  const response = await fetch('/api/deck?deck=' + encodeURIComponent(key));
  if (!response.ok) { deckGrid.textContent = 'This deck could not be opened. Please try again.'; return; }
  const loaded = await response.json();
  if (key !== deckSelect.value) return;
  deck = loaded;
  seedEl.textContent = `${deck.length} cards`;
  renderDeck();
}

function openCard(card) {
  selectedCard = card;
  document.querySelector("#detail-image").src = card.image_url;
  document.querySelector("#detail-image").alt = card.name;
  document.querySelector("#detail-kicker").textContent = [card.arcana, card.suit].filter(Boolean).join(" / ");
  document.querySelector("#detail-name").textContent = card.name;
  document.querySelector("#detail-celebrity").textContent = card.celebrity ? `Deck persona: ${card.celebrity}` : "";
  document.querySelector("#detail-upright").textContent = card.upright;
  document.querySelector("#detail-reversed").textContent = card.reversed;
  document.querySelector("#detail-domain").textContent = card.domain;
  document.querySelector("#detail-snippet").textContent = card.seed_text;
  cardAudio.hidden = true;
  cardAudio.removeAttribute("src");
  cardDialog.showModal();
}

async function speakCard() {
  if (!selectedCard) return;
  speakCardButton.disabled = true;
  speakCardButton.querySelector("span").textContent = "Reading...";
  document.querySelector("#detail-snippet").textContent = "Preparing this card's spoken meaning...";
  cardAudio.hidden = true;
  cardAudio.removeAttribute("src");

  try {
    const response = await fetch(`/api/cards/${selectedCard.id}/snippet?deck=${encodeURIComponent(selectedCard.deck || 'celebrity')}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        focus: document.querySelector("#question").value,
        use_ai: document.querySelector("#card-use-ai").checked,
        use_voice: document.querySelector("#card-use-voice").checked,
      }),
    });
    if (!response.ok) throw new Error(`Snippet failed: ${response.status}`);
    const result = await response.json();
    document.querySelector("#detail-snippet").textContent = result.text;
    if (result.audio_url) {
      cardAudio.src = result.audio_url;
      cardAudio.hidden = false;
      cardAudio.play().catch(() => {});
    }
  } catch (error) {
    document.querySelector("#detail-snippet").textContent = selectedCard.seed_text;
  } finally {
    speakCardButton.disabled = false;
    speakCardButton.querySelector("span").textContent = "Card Reading";
  }
}

function openDeckPanel() {
  setPanel("deck");
  document.querySelector(".reading-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

dealButton.addEventListener("click", deal);
mobileDealButton.addEventListener("click", deal);
browseDeckButton.addEventListener("click", openDeckPanel);
mobileDeckButton.addEventListener("click", openDeckPanel);
readingTab.addEventListener("click", () => setPanel("reading"));
deckTab.addEventListener("click", () => setPanel("deck"));
deckGroup.addEventListener("change", renderDeck);
deckSearch.addEventListener("input", renderDeck);
closeCardButton.addEventListener("click", () => cardDialog.close());
speakCardButton.addEventListener("click", speakCard);
deckSelect.addEventListener('change', () => {
  deck = [];
  cardDialog.close();
  cardAudio.pause();
  if (!deckLibrary.hidden) loadDeck();
});
