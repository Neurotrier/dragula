const elements = {
  aiResult: document.getElementById("aiResult"),
  deleteDescriptionsBtn: document.getElementById("deleteDescriptionsBtn"),
  describeBtn: document.getElementById("describeBtn"),
  descriptionLoading: document.getElementById("descriptionLoading"),
  feedbackMessage: document.getElementById("feedbackMessage"),
  symbolCount: document.getElementById("symbolCount"),
  symbolDetails: document.getElementById("symbolDetails"),
  symbolList: document.getElementById("symbolList"),
  symbolListStatus: document.getElementById("symbolListStatus"),
  symbolSearchInput: document.getElementById("symbolSearchInput"),
};

const state = {
  activeSelectionRequest: 0,
  allSymbols: [],
  detailCache: new Map(),
  detailLoadingTimeoutId: null,
  filteredSymbols: [],
  isDescriptionLoading: false,
  selectedSymbolId: null,
};

let searchDebounceId = null;

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setActionState() {
  const hasSelection = Boolean(state.selectedSymbolId);
  const disableActions = !hasSelection || state.isDescriptionLoading;
  elements.describeBtn.disabled = disableActions;
  elements.deleteDescriptionsBtn.disabled = disableActions;
}

function setDescriptionLoading(isLoading) {
  state.isDescriptionLoading = isLoading;
  elements.descriptionLoading.classList.toggle("hidden", !isLoading);
  setActionState();
}

function setFeedback(message, tone = "info") {
  if (!message) {
    elements.feedbackMessage.classList.add("hidden");
    elements.feedbackMessage.textContent = "";
    elements.feedbackMessage.removeAttribute("data-tone");
    return;
  }

  elements.feedbackMessage.textContent = message;
  elements.feedbackMessage.dataset.tone = tone;
  elements.feedbackMessage.classList.remove("hidden");
}

function setResult(content, isPlaceholder = false) {
  elements.aiResult.textContent = content;
  elements.aiResult.classList.toggle("empty-result", isPlaceholder);
}

function updateSymbolCount(visibleCount) {
  const totalCount = state.allSymbols.length;
  elements.symbolCount.textContent = totalCount === visibleCount ? String(totalCount) : `${visibleCount}/${totalCount}`;
}

function updateSymbolListStatus(symbols, query) {
  if (!state.allSymbols.length) {
    elements.symbolListStatus.textContent = "No indexed objects were found yet.";
    return;
  }

  if (!symbols.length) {
    elements.symbolListStatus.textContent = query
      ? `No objects match "${query}".`
      : "No indexed objects are available.";
    return;
  }

  if (query) {
    elements.symbolListStatus.textContent = `Showing ${symbols.length} matching object${symbols.length === 1 ? "" : "s"}.`;
    return;
  }

  elements.symbolListStatus.textContent = `Showing ${symbols.length} indexed object${symbols.length === 1 ? "" : "s"}.`;
}

function renderSymbolDetails(symbol, chunks) {
  elements.symbolDetails.classList.remove("is-loading");
  elements.symbolDetails.classList.remove("empty-state");
  elements.symbolDetails.innerHTML = `
    <h3 class="details-heading">${escapeHtml(symbol.qualified_name || "Unnamed object")}</h3>
    <dl class="details-grid">
      <div class="detail-row">
        <dt>Kind</dt>
        <dd>${escapeHtml(symbol.kind || "-")}</dd>
      </div>
      <div class="detail-row">
        <dt>File</dt>
        <dd>${escapeHtml(symbol.file_path || "-")}</dd>
      </div>
      <div class="detail-row">
        <dt>Signature</dt>
        <dd>${escapeHtml(symbol.signature || "-")}</dd>
      </div>
      <div class="detail-row">
        <dt>Chunks</dt>
        <dd>${chunks.length}</dd>
      </div>
    </dl>
  `;
}

function renderDetailsLoadingState() {
  elements.symbolDetails.classList.remove("is-loading");
  elements.symbolDetails.classList.add("empty-state");
  elements.symbolDetails.innerHTML = `
    <p class="empty-title">Loading details</p>
    <p class="empty-copy">Fetching metadata for the selected object.</p>
  `;
}

function renderDetailsErrorState(message) {
  elements.symbolDetails.classList.remove("is-loading");
  elements.symbolDetails.classList.add("empty-state");
  elements.symbolDetails.innerHTML = `
    <p class="empty-title">Unable to load details</p>
    <p class="empty-copy">${escapeHtml(message || "The object details could not be loaded.")}</p>
  `;
}

function clearDetailsLoadingState() {
  window.clearTimeout(state.detailLoadingTimeoutId);
  state.detailLoadingTimeoutId = null;
  elements.symbolDetails.classList.remove("is-loading");
}

function scheduleDetailsLoadingState() {
  clearDetailsLoadingState();
  state.detailLoadingTimeoutId = window.setTimeout(() => {
    const hasRenderedDetails = !elements.symbolDetails.classList.contains("empty-state");
    if (hasRenderedDetails) {
      elements.symbolDetails.classList.add("is-loading");
      return;
    }

    renderDetailsLoadingState();
  }, 180);
}

function renderSymbols(symbols) {
  const fragment = document.createDocumentFragment();

  for (const symbol of symbols) {
    const li = document.createElement("li");
    const button = document.createElement("button");
    const kind = document.createElement("span");
    const name = document.createElement("span");

    button.type = "button";
    button.className = "symbol-button";
    button.dataset.symbolId = symbol.id;
    button.classList.toggle("is-active", symbol.id === state.selectedSymbolId);

    kind.className = "symbol-button-kind";
    kind.textContent = symbol.kind || "object";

    name.className = "symbol-button-name";
    name.textContent = symbol.qualified_name || symbol.id;

    button.append(kind, name);
    li.appendChild(button);
    fragment.appendChild(li);
  }

  elements.symbolList.replaceChildren(fragment);
}

function updateActiveSymbolButton(nextSymbolId) {
  const currentActiveButton = elements.symbolList.querySelector(".symbol-button.is-active");
  if (currentActiveButton?.dataset.symbolId === nextSymbolId) {
    return;
  }

  currentActiveButton?.classList.remove("is-active");
  const nextActiveButton = elements.symbolList.querySelector(`.symbol-button[data-symbol-id="${CSS.escape(nextSymbolId)}"]`);
  nextActiveButton?.classList.add("is-active");
}

function filterSymbolsByName(query) {
  const normalizedQuery = query.trim().toLowerCase();
  state.filteredSymbols = normalizedQuery
    ? state.allSymbols.filter((symbol) => (symbol.qualified_name || "").toLowerCase().includes(normalizedQuery))
    : state.allSymbols;

  renderSymbols(state.filteredSymbols);
  updateSymbolCount(state.filteredSymbols.length);
  updateSymbolListStatus(state.filteredSymbols, query.trim());
}

function debounceFilter(query) {
  window.clearTimeout(searchDebounceId);
  searchDebounceId = window.setTimeout(() => {
    filterSymbolsByName(query);
  }, 150);
}

async function readErrorMessage(response, fallbackMessage) {
  try {
    const payload = await response.json();
    return payload.detail || fallbackMessage;
  } catch {
    return fallbackMessage;
  }
}

async function loadSymbols() {
  elements.symbolListStatus.textContent = "Loading indexed objects...";

  try {
    const response = await fetch("/api/symbols");
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, "Failed to load indexed objects."));
    }

    state.allSymbols = await response.json();
    filterSymbolsByName(elements.symbolSearchInput.value);
  } catch (error) {
    state.allSymbols = [];
    state.filteredSymbols = [];
    renderSymbols([]);
    updateSymbolCount(0);
    updateSymbolListStatus([], "");
    setFeedback(error.message || "Failed to load indexed objects.", "error");
  }
}

async function selectSymbol(symbolId) {
  if (!symbolId) {
    return;
  }

  state.selectedSymbolId = symbolId;
  setActionState();
  updateActiveSymbolButton(symbolId);
  setFeedback("");

  const requestId = state.activeSelectionRequest + 1;
  state.activeSelectionRequest = requestId;

  const cached = state.detailCache.get(symbolId);
  if (cached) {
    clearDetailsLoadingState();
    renderSymbolDetails(cached.symbol, cached.chunks);
    return;
  }

  scheduleDetailsLoadingState();

  try {
    const response = await fetch(`/api/symbols/${symbolId}`);
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, "Failed to load object details."));
    }

    const data = await response.json();
    if (requestId !== state.activeSelectionRequest) {
      return;
    }

    clearDetailsLoadingState();
    const chunks = data.chunks || [];
    state.detailCache.set(symbolId, { symbol: data.symbol, chunks });
    renderSymbolDetails(data.symbol, chunks);
  } catch (error) {
    if (requestId !== state.activeSelectionRequest) {
      return;
    }

    clearDetailsLoadingState();
    renderDetailsErrorState(error.message);
    setFeedback(error.message || "Failed to load object details.", "error");
  }
}

async function describeCurrent() {
  if (!state.selectedSymbolId) {
    return;
  }

  setDescriptionLoading(true);
  setFeedback("");
  setResult("Generating AI description...", true);

  try {
    const response = await fetch(`/api/symbols/${state.selectedSymbolId}/describe`, { method: "POST" });
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, "Failed to generate AI description."));
    }

    const data = await response.json();
    setResult(JSON.stringify(data, null, 2));
    setFeedback("Description generated successfully.", "success");
  } catch (error) {
    setResult("No AI output yet. Generate a description to see the response here.", true);
    setFeedback(error.message || "Failed to generate AI description.", "error");
  } finally {
    setDescriptionLoading(false);
  }
}

async function deleteDescriptionsForCurrentSymbol() {
  if (!state.selectedSymbolId) {
    return;
  }

  setFeedback("");

  try {
    const response = await fetch(`/api/symbols/${state.selectedSymbolId}/descriptions`, { method: "DELETE" });
    if (!response.ok) {
      throw new Error(await readErrorMessage(response, "Failed to delete AI description data."));
    }

    const data = await response.json();
    setResult(`Deleted AI description records: ${data.deleted}`);
    setFeedback("Stored descriptions were deleted.", "success");
  } catch (error) {
    setFeedback(error.message || "Failed to delete AI description data.", "error");
  }
}

elements.describeBtn.addEventListener("click", describeCurrent);
elements.deleteDescriptionsBtn.addEventListener("click", deleteDescriptionsForCurrentSymbol);
elements.symbolSearchInput.addEventListener("input", (event) => {
  debounceFilter(event.target.value);
});
elements.symbolList.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-symbol-id]");
  if (!button) {
    return;
  }

  selectSymbol(button.dataset.symbolId);
});

setActionState();
loadSymbols();
