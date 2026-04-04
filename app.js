const tabs = [
  { id: "pokemon", label: "Pokemon" },
  { id: "moves", label: "Moves" },
  { id: "abilities", label: "Abilities" },
  { id: "items", label: "Items" },
  { id: "trainers", label: "Trainers" },
  { id: "rules", label: "Rules" },
];

const typeColors = {
  Normal: "#cfd4dd",
  Fire: "#ff956c",
  Water: "#72c7ff",
  Electric: "#ffd86b",
  Grass: "#7ce299",
  Ice: "#97f2ff",
  Fighting: "#ff8e8e",
  Poison: "#d49bff",
  Ground: "#d7b57c",
  Flying: "#a5c1ff",
  Psychic: "#ff8fbf",
  Bug: "#b5dc75",
  Rock: "#ccb072",
  Ghost: "#9b96ff",
  Dragon: "#7ea4ff",
  Dark: "#8a7f77",
  Steel: "#a9c2cf",
  Fairy: "#ffbde2",
};

const MOBILE_BREAKPOINT = 1040;
const LIST_BATCH_DESKTOP = 120;
const LIST_BATCH_MOBILE = 48;

const els = {
  tabs: document.getElementById("tabs"),
  list: document.getElementById("list"),
  detail: document.getElementById("detail"),
  detailPanel: document.getElementById("detail-panel"),
  listTitle: document.getElementById("list-title"),
  listCount: document.getElementById("list-count"),
  search: document.getElementById("search"),
  statsStrip: document.getElementById("stats-strip"),
};

const state = {
  data: null,
  tab: "pokemon",
  query: "",
  selectedId: null,
  visibleCount: 0,
};

function byId(entries) {
  return new Map(entries.map((entry) => [entry.id, entry]));
}

function isMobileLayout() {
  return window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`).matches;
}

function getListBatchSize() {
  return isMobileLayout() ? LIST_BATCH_MOBILE : LIST_BATCH_DESKTOP;
}

function resetVisibleCount() {
  state.visibleCount = getListBatchSize();
}

function scrollDetailIntoView() {
  if (!isMobileLayout()) return;
  requestAnimationFrame(() => {
    els.detailPanel?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function selectEntry(id, options = {}) {
  state.selectedId = id;
  render();
  if (options.scrollMobile) {
    scrollDetailIntoView();
  }
}

function buildIndexes(data) {
  data.speciesById = byId(data.species);
  data.movesById = byId(data.moves);
  data.abilitiesById = byId(data.abilities);
  data.itemsById = byId(data.items);
  data.itemIdByName = new Map(data.items.map((item) => [item.name.toLowerCase(), item.id]));
}

function renderTabs() {
  els.tabs.innerHTML = "";
  for (const tab of tabs) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `tab${state.tab === tab.id ? " active" : ""}`;
    button.textContent = tab.label;
    button.addEventListener("click", () => {
      state.tab = tab.id;
      state.selectedId = null;
      resetVisibleCount();
      render();
    });
    els.tabs.appendChild(button);
  }
}

function renderStats() {
  const stats = [
    { label: "Pokemon", value: state.data.species.length },
    { label: "Moves", value: state.data.moves.length },
    { label: "Abilities", value: state.data.abilities.length },
    { label: "Items", value: state.data.items.length },
    { label: "Trainers", value: state.data.trainers.length },
  ];
  els.statsStrip.innerHTML = stats
    .map((stat) => `<div class="stat-card"><span class="muted">${stat.label}</span><strong>${stat.value}</strong></div>`)
    .join("");
}

function getEntriesForTab() {
  const query = state.query.trim().toLowerCase();
  if (state.tab === "pokemon") {
    return state.data.species.filter((entry) =>
      [entry.id, entry.name, ...(entry.types || []), ...(entry.abilities || []).map((ability) => ability.name)]
        .join(" ")
        .toLowerCase()
        .includes(query),
    );
  }
  if (state.tab === "moves") {
    return state.data.moves.filter((entry) =>
      [entry.id, entry.name, entry.type, entry.category, entry.description].join(" ").toLowerCase().includes(query),
    );
  }
  if (state.tab === "abilities") {
    return state.data.abilities.filter((entry) =>
      [entry.id, entry.name, entry.description].join(" ").toLowerCase().includes(query),
    );
  }
  if (state.tab === "items") {
    return state.data.items.filter((entry) =>
      [entry.id, entry.name, entry.description, entry.pocket].join(" ").toLowerCase().includes(query),
    );
  }
  if (state.tab === "trainers") {
    return state.data.trainers.filter((entry) =>
      [entry.idToken, entry.name, entry.class, ...entry.pokemon.map((mon) => mon.speciesName)].join(" ").toLowerCase().includes(query),
    );
  }
  return [];
}

function ensureSelection(entries) {
  if (state.tab === "rules") {
    state.selectedId = "rules";
    return;
  }
  if (!entries.length) {
    state.selectedId = null;
    return;
  }
  const hasCurrent = entries.some((entry) => String(entry.id ?? entry.idToken) === String(state.selectedId));
  if (!hasCurrent) {
    state.selectedId = entries[0].id ?? entries[0].idToken;
  }
}

function typeChip(type) {
  const color = typeColors[type] || "#9fb3c8";
  return `<span class="chip type" style="background:${color}">${type}</span>`;
}

function moveNames(ids) {
  return (ids || [])
    .map((id) => state.data.movesById.get(id))
    .filter(Boolean)
    .map((move) => move.name);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function navButton(tab, id, label) {
  return `<button type="button" class="chip nav-chip" data-nav-tab="${tab}" data-nav-id="${id}">${escapeHtml(label)}</button>`;
}

function setDetailHtml(html, options = {}) {
  els.detail.className = options.empty ? "detail empty-state" : "detail";
  els.detail.innerHTML = html;
}

function renderList(entries) {
  els.listTitle.textContent = tabs.find((tab) => tab.id === state.tab)?.label ?? state.tab;

  if (state.tab === "rules") {
    els.listCount.textContent = "Snapshot";
    els.list.innerHTML = `<div class="detail-card"><strong>${state.data.project.title}</strong><p>${state.data.project.subtitle}</p></div>`;
    return;
  }

  const visibleEntries = entries.slice(0, state.visibleCount);
  els.listCount.textContent = visibleEntries.length < entries.length ? `${entries.length} entries • ${visibleEntries.length} shown` : `${entries.length} entries`;

  if (!entries.length) {
    els.list.innerHTML = `<div class="detail-card"><strong>No results</strong><p>Try a broader search.</p></div>`;
    return;
  }

  els.list.innerHTML = "";
  for (const entry of visibleEntries) {
    const id = entry.id ?? entry.idToken;
    const button = document.createElement("button");
    button.type = "button";
    button.className = `list-item${String(state.selectedId) === String(id) ? " active" : ""}`;

    const icon =
      state.tab === "pokemon" && entry.icon
        ? `<img class="pokemon-icon" src="${entry.icon}" alt="${entry.name}" loading="lazy" decoding="async" />`
        : `<div></div>`;

    let sub = "";
    if (state.tab === "pokemon") sub = (entry.types || []).join(" / ");
    if (state.tab === "moves") sub = entry.description?.replace(/\n/g, " ") || [entry.type, entry.category].filter(Boolean).join(" • ");
    if (state.tab === "abilities") sub = entry.description || `${(entry.speciesIds || []).length} linked species`;
    if (state.tab === "items") sub = entry.description || [entry.pocket?.replace("POCKET_", ""), entry.price ? `${entry.price}$` : ""].filter(Boolean).join(" • ");
    if (state.tab === "trainers") sub = `${entry.class || "Trainer"} • ${(entry.pokemon || []).length} mon`;

    button.innerHTML = `${icon}<div><div class="list-item-title">${entry.name ?? entry.idToken}</div><div class="list-item-sub">${sub}</div></div><div class="muted">ID: ${id}</div>`;
    button.addEventListener("click", () => {
      selectEntry(id, { scrollMobile: true });
    });
    els.list.appendChild(button);
  }

  if (visibleEntries.length < entries.length) {
    const moreButton = document.createElement("button");
    moreButton.type = "button";
    moreButton.className = "show-more";
    moreButton.textContent = `Show ${Math.min(getListBatchSize(), entries.length - visibleEntries.length)} more`;
    moreButton.addEventListener("click", () => {
      state.visibleCount += getListBatchSize();
      render();
    });
    els.list.appendChild(moreButton);
  }
}

function renderPokemonDetail(entry) {
  const abilities = Array.isArray(entry.abilities) ? entry.abilities : [];
  const evolutions = Array.isArray(entry.evolutions) ? entry.evolutions : [];
  const teachable = entry.teachable || { all: [], tmhm: [], tutor: [], special: [] };
  const moveLevels = Array.isArray(entry.moveLevels) ? entry.moveLevels : [];
  const eggMoves = Array.isArray(entry.eggMoves) ? entry.eggMoves : [];
  const types = Array.isArray(entry.types) ? entry.types : [];

  const abilityCards = abilities.length
    ? abilities
        .map(
          (ability) => `
            <div class="detail-card">
              <h4>ID: ${ability.id} ${ability.name}</h4>
              <p>${ability.description || "No description available."}</p>
            </div>
          `,
        )
        .join("")
    : `<div class="detail-card"><h4>No abilities</h4><p>No linked abilities in the current snapshot.</p></div>`;

  const evoCards = evolutions.length
    ? evolutions
        .map(
          (evo) => `
            <div class="detail-card">
              <h4>${evo.targetName || `ID: ${evo.targetSpecies}`}</h4>
              <p>${evo.label}</p>
            </div>
          `,
        )
        .join("")
    : `<div class="detail-card"><h4>No evolutions</h4><p>This entry has no forward evolutions in the current snapshot.</p></div>`;

  const teachableGroups = [
    { title: "TM / HM", ids: teachable.tmhm || [] },
    { title: "Tutor", ids: teachable.tutor || [] },
    { title: "Other Teachables", ids: teachable.special || [] },
    { title: "Egg Moves", ids: eggMoves },
  ];

  const teachableHtml = teachableGroups
    .map(({ title, ids }) => {
      const names = moveNames(ids);
      return `
        <div class="detail-card">
          <h4>${title}</h4>
          ${
            names.length
              ? `<ul class="plain-list">${names.map((name) => `<li>${name}</li>`).join("")}</ul>`
              : `<p>No entries in this group.</p>`
          }
        </div>
      `;
    })
    .join("");

  setDetailHtml(`
    <div class="detail-hero">
      <div class="detail-title">
        <h2>${entry.name}</h2>
        <p>ID: ${entry.id} • ${entry.token}</p>
      </div>
      ${entry.icon ? `<div class="pokemon-icon-zoom"><img class="pokemon-icon" src="${entry.icon}" alt="${entry.name}" decoding="async" /></div>` : ""}
    </div>

    <div class="chip-row" style="margin-top:18px;">${types.map(typeChip).join("")}</div>

    <div class="detail-grid">
      <div class="detail-box"><span class="muted">BST</span><strong>${entry.bst ?? "-"}</strong></div>
      <div class="detail-box"><span class="muted">Weight</span><strong>${entry.weight ? `${entry.weight} kg` : "-"}</strong></div>
      <div class="detail-box"><span class="muted">Learnset Levels</span><strong>${moveLevels.length}</strong></div>
      <div class="detail-box"><span class="muted">Teachables</span><strong>${(teachable.all || []).length}</strong></div>
    </div>

    <div class="detail-section">
      <h3>Abilities</h3>
      <div class="detail-section-list">${abilityCards}</div>
    </div>

    <div class="detail-section">
      <h3>Evolutions</h3>
      <div class="detail-section-list">${evoCards}</div>
    </div>

    <div class="detail-section">
      <h3>Learnset Levels</h3>
      <div class="chip-row">
        ${
          moveLevels.length
            ? moveLevels.map((level) => `<span class="chip">Lv ${level}</span>`).join("")
            : `<span class="chip">No level data</span>`
        }
      </div>
    </div>

    <div class="detail-section">
      <h3>Teachables / Egg</h3>
      <div class="detail-section-list">${teachableHtml}</div>
    </div>
  `);
}

function renderMoveDetail(entry) {
  setDetailHtml(`
    <div class="detail-hero">
      <div class="detail-title">
        <h2>${entry.name}</h2>
        <p>ID: ${entry.id} • ${entry.type} • ${entry.category}</p>
      </div>
    </div>
    <div class="chip-row">
      ${entry.type ? typeChip(entry.type) : ""}
      ${entry.category ? `<span class="chip">${entry.category}</span>` : ""}
      ${entry.priority ? `<span class="chip">Priority ${entry.priority}</span>` : ""}
    </div>
    <div class="detail-grid">
      <div class="detail-box"><span class="muted">Power</span><strong>${entry.power ?? "-"}</strong></div>
      <div class="detail-box"><span class="muted">Accuracy</span><strong>${entry.accuracy ?? "-"}</strong></div>
      <div class="detail-box"><span class="muted">PP</span><strong>${entry.pp ?? "-"}</strong></div>
      <div class="detail-box"><span class="muted">Target</span><strong>${entry.target ? entry.target.replace("TARGET_", "") : "-"}</strong></div>
    </div>
    <div class="detail-section">
      <h3>Description</h3>
      <div class="detail-card"><p>${entry.description || "No description available."}</p></div>
    </div>
  `);
}

function renderAbilityDetail(entry) {
  const species = (entry.speciesIds || []).map((id) => state.data.speciesById.get(id)).filter(Boolean);
  setDetailHtml(`
    <div class="detail-hero">
      <div class="detail-title">
        <h2>${entry.name}</h2>
        <p>ID: ${entry.id} • ${species.length} linked species</p>
      </div>
    </div>
    <div class="detail-section">
      <h3>Description</h3>
      <div class="detail-card"><p>${entry.description || "No description available."}</p></div>
    </div>
    <div class="detail-section">
      <h3>Pokemon Using This Ability</h3>
      <div class="chip-row">${species.map((pokemon) => navButton("pokemon", pokemon.id, pokemon.name)).join("") || `<span class="chip">No linked species</span>`}</div>
    </div>
  `);
}

function renderItemDetail(entry) {
  setDetailHtml(`
    <div class="detail-hero">
      <div class="detail-title">
        <h2>${entry.name}</h2>
        <p>ID: ${entry.id} • ${entry.token}</p>
      </div>
    </div>
    <div class="detail-grid">
      <div class="detail-box"><span class="muted">Pocket</span><strong>${entry.pocket ? entry.pocket.replace("POCKET_", "") : "-"}</strong></div>
      <div class="detail-box"><span class="muted">Price</span><strong>${entry.price || "-"}</strong></div>
    </div>
    <div class="detail-section">
      <h3>Description</h3>
      <div class="detail-card"><p>${entry.description || "No description available."}</p></div>
    </div>
  `);
}

function renderTrainerDetail(entry) {
  const party = (entry.pokemon || [])
    .map(
      (mon) => `
        <div class="detail-card trainer-mon">
          <h4>${mon.speciesId ? navButton("pokemon", mon.speciesId, mon.speciesName) : escapeHtml(mon.speciesName)}${mon.level ? ` • Lv ${mon.level}` : ""}</h4>
          <p>${escapeHtml([mon.ability, mon.item].filter(Boolean).join(" • ") || "No extra metadata")}</p>
          ${
            (mon.moves || []).length
              ? `<ul class="plain-list">${mon.moves.map((move) => `<li>${escapeHtml(move)}</li>`).join("")}</ul>`
              : ""
          }
        </div>
      `,
    )
    .join("");

  const trainerItems = (entry.items || []).length
    ? entry.items
        .map((item) => {
          const itemId = state.data.itemIdByName.get(String(item).toLowerCase());
          return itemId ? navButton("items", itemId, item) : `<span class="chip">${escapeHtml(item)}</span>`;
        })
        .join("")
    : `<span class="chip">No trainer items</span>`;

  setDetailHtml(`
    <div class="detail-hero">
      <div class="detail-title">
        <h2>${entry.name || entry.idToken}</h2>
        <p>ID: ${entry.idToken} • ${entry.class || "Trainer"}</p>
      </div>
    </div>
    <div class="detail-grid">
      <div class="detail-box"><span class="muted">Pic</span><strong>${entry.pic || "-"}</strong></div>
      <div class="detail-box"><span class="muted">Gender</span><strong>${entry.gender || "-"}</strong></div>
      <div class="detail-box"><span class="muted">Battle Type</span><strong>${entry.battleType || "-"}</strong></div>
      <div class="detail-box"><span class="muted">Party Size</span><strong>${(entry.pokemon || []).length}</strong></div>
    </div>
    <div class="detail-section">
      <h3>Trainer Items</h3>
      <div class="chip-row">${trainerItems}</div>
    </div>
    <div class="detail-section">
      <h3>Party Snapshot</h3>
      <div class="trainer-party">${party || `<div class="detail-card"><p>No party data available.</p></div>`}</div>
    </div>
  `);
}

function renderRulesDetail() {
  setDetailHtml(`
    <div class="detail-hero">
      <div class="detail-title">
        <h2>${state.data.project.title}</h2>
        <p>${state.data.project.subtitle}</p>
      </div>
    </div>
    <div class="detail-section detail-section-list">
      ${state.data.project.sections
        .map(
          (section) => `
            <div class="detail-card">
              <h4>${section.title}</h4>
              <ul class="rules-list">${section.items.map((item) => `<li>${item}</li>`).join("")}</ul>
            </div>
          `,
        )
        .join("")}
    </div>
  `);
}

function renderDetail(entries) {
  if (state.tab === "rules") {
    renderRulesDetail();
    return;
  }

  const entry = entries.find((item) => String(item.id ?? item.idToken) === String(state.selectedId));
  if (!entry) {
    setDetailHtml(`<h2>No selection</h2><p>Choose an entry from the list.</p>`, { empty: true });
    return;
  }

  if (state.tab === "pokemon") renderPokemonDetail(entry);
  if (state.tab === "moves") renderMoveDetail(entry);
  if (state.tab === "abilities") renderAbilityDetail(entry);
  if (state.tab === "items") renderItemDetail(entry);
  if (state.tab === "trainers") renderTrainerDetail(entry);
}

function render() {
  renderTabs();
  renderStats();
  const entries = getEntriesForTab();
  ensureSelection(entries);
  renderList(entries);
  renderDetail(entries);
}

async function init() {
  resetVisibleCount();
  const response = await fetch("data/site-data.json");
  state.data = await response.json();
  buildIndexes(state.data);

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-nav-tab][data-nav-id]");
    if (!button) return;
    state.tab = button.dataset.navTab;
    state.selectedId = button.dataset.navId;
    state.query = "";
    resetVisibleCount();
    els.search.value = "";
    render();
    scrollDetailIntoView();
  });

  els.search.addEventListener("input", (event) => {
    state.query = event.target.value;
    resetVisibleCount();
    render();
  });

  window.addEventListener("resize", () => {
    state.visibleCount = Math.max(state.visibleCount, getListBatchSize());
  });

  render();
}

init().catch((error) => {
  console.error(error);
  setDetailHtml(`<h2>Data load failed</h2><p>Open the console for details.</p>`, { empty: true });
});
