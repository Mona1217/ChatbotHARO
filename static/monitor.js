(function () {
  const body = document.body;
  const query = new URLSearchParams(window.location.search);

  function readTemplateSafe(value) {
    if (!value) {
      return "";
    }
    if (value.includes("{{") || value.includes("}}")) {
      return "";
    }
    return value;
  }

  const token = readTemplateSafe(body.dataset.token) || query.get("token") || "";
  const providedEventsUrl = readTemplateSafe(body.dataset.eventsUrl) || "";
  const providedPauseUrl = readTemplateSafe(body.dataset.pauseUrl) || "";
  const providedStreamUrl = readTemplateSafe(body.dataset.streamUrl) || "";
  const providedExportUrl = readTemplateSafe(body.dataset.exportUrl) || "";
  const providedExportChatUrl = readTemplateSafe(body.dataset.exportChatUrl) || "";
  const explicitApiBaseRaw = readTemplateSafe(query.get("api_base")) || readTemplateSafe(query.get("api")) || "";
  const explicitApiBase = explicitApiBaseRaw.replace(/\/+$/, "");
  const pollInput = readTemplateSafe(body.dataset.pollSeconds) || query.get("poll") || "5";
  const pollParsed = Number.parseInt(pollInput, 10);
  const pollSeconds = Number.isFinite(pollParsed) && pollParsed > 0 ? pollParsed : 5;

  const contactsList = document.getElementById("contactsList");
  const contactsEmpty = document.getElementById("contactsEmpty");
  const contactsMeta = document.getElementById("contactsMeta");
  const chatTimeline = document.getElementById("chatTimeline");
  const chatEmpty = document.getElementById("chatEmpty");
  const errorState = document.getElementById("errorState");
  const eventCount = document.getElementById("eventCount");
  const contactCount = document.getElementById("contactCount");
  const lastUpdate = document.getElementById("lastUpdate");
  const statusBadge = document.getElementById("botStatus");
  const exportBtn = document.getElementById("exportNumbersBtn");
  const exportChatBtn = document.getElementById("exportChatBtn");
  const toggleBtn = document.getElementById("togglePauseBtn");
  const refreshBtn = document.getElementById("refreshBtn");
  const activeContact = document.getElementById("activeContact");
  const activeMeta = document.getElementById("activeMeta");
  const backToContactsBtn = document.getElementById("backToContactsBtn");
  const mobileViewport = window.matchMedia("(max-width: 760px)");

  const state = {
    paused: false,
    selectedPeer: null,
    contacts: [],
    allEvents: [],
    conversationByPeer: {},
    totalEvents: 0,
    version: 0,
    stream: null,
    streamRetryTimer: null,
    mobileView: "contacts",
  };

  const cache = {
    key: "haro_monitor_cache_v1",
    maxEvents: 800,
  };

  function loadCachedState() {
    try {
      const raw = window.localStorage.getItem(cache.key);
      if (!raw) {
        return false;
      }
      const data = JSON.parse(raw);
      const events = Array.isArray(data?.events) ? data.events : [];
      if (!events.length) {
        return false;
      }
      const normalizedEvents = events.slice(-cache.maxEvents);
      state.allEvents = normalizedEvents;
      state.totalEvents = Number(data?.total || normalizedEvents.length || 0);
      state.version = Number(data?.version || 0);
      state.selectedPeer = data?.selectedPeer || state.selectedPeer;
      renderAll(state.allEvents);
      lastUpdate.textContent = "Historial cargado (cache local)";
      return true;
    } catch {
      return false;
    }
  }

  function persistCachedState() {
    try {
      const events = Array.isArray(state.allEvents) ? state.allEvents.slice(-cache.maxEvents) : [];
      if (!events.length) {
        return;
      }
      window.localStorage.setItem(
        cache.key,
        JSON.stringify({
          version: state.version,
          total: state.totalEvents,
          selectedPeer: state.selectedPeer,
          events,
        }),
      );
    } catch {
      // Ignora errores de cuota / JSON / modo privado.
    }
  }

  function withToken(url) {
    if (!token) {
      return url;
    }
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}token=${encodeURIComponent(token)}`;
  }

  function getProvidedUrl(kind) {
    if (kind === "events") {
      return providedEventsUrl;
    }
    if (kind === "pause") {
      return providedPauseUrl;
    }
    if (kind === "stream") {
      return providedStreamUrl;
    }
    if (kind === "export") {
      return providedExportUrl;
    }
    if (kind === "export_chat") {
      return providedExportChatUrl;
    }
    return "";
  }

  function isLocalDevelopmentHost(hostname) {
    return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "[::1]";
  }

  function getApiBaseCandidates() {
    const candidates = [];
    const seen = new Set();
    const protocol = window.location.protocol;
    const hostname = window.location.hostname;
    const port = window.location.port;

    function add(base) {
      const normalized = (base || "").replace(/\/+$/, "");
      if (seen.has(normalized)) {
        return;
      }
      seen.add(normalized);
      candidates.push(normalized);
    }

    if (explicitApiBase) {
      add(explicitApiBase);
    }

    if (!explicitApiBase && protocol.startsWith("http") && hostname && port && port !== "8000" && isLocalDevelopmentHost(hostname)) {
      add(`${protocol}//${hostname}:8000`);
    }

    if (!explicitApiBase && (protocol === "file:" || isLocalDevelopmentHost(hostname))) {
      add("http://127.0.0.1:8000");
      add("http://localhost:8000");
    }

    add("");

    return candidates;
  }

  function getEndpointCandidates(kind) {
    const candidates = [];
    const seen = new Set();
    const path = window.location.pathname.replace(/\/+$/, "");
    const directMonitorPath =
      kind === "export"
        ? "/monitor/export/contacts.xlsx"
        : kind === "export_chat"
          ? "/monitor/export/chat.xlsx"
          : `/monitor/${kind}`;
    const directApiPath =
      kind === "export"
        ? "/api/monitor/export/contacts.xlsx"
        : kind === "export_chat"
          ? "/api/monitor/export/chat.xlsx"
          : `/api/monitor/${kind}`;

    function add(rawPath) {
      const normalized = rawPath.startsWith("/") ? rawPath : `/${rawPath}`;
      if (seen.has(normalized)) {
        return;
      }
      seen.add(normalized);
      candidates.push(normalized);
    }

    add(directMonitorPath);
    add(directApiPath);

    if (path.endsWith("/monitor")) {
      const base = path.slice(0, -"/monitor".length);
      add(`${base}${directMonitorPath}`);
      add(`${base}${directApiPath}`);
    }

    if (path.endsWith("/static/monitor.html")) {
      const base = path.slice(0, -"/static/monitor.html".length);
      add(`${base}${directMonitorPath}`);
      add(`${base}${directApiPath}`);
    }

    return candidates;
  }

  function composeCandidateUrls(kind) {
    const bases = getApiBaseCandidates();
    const paths = getEndpointCandidates(kind);
    const urls = [];
    const seen = new Set();
    const providedUrl = getProvidedUrl(kind);

    if (providedUrl) {
      const directUrl = withToken(providedUrl);
      seen.add(directUrl);
      urls.push(directUrl);
    }

    for (const base of bases) {
      for (const path of paths) {
        const url = withToken(base ? `${base}${path}` : path);
        if (seen.has(url)) {
          continue;
        }
        seen.add(url);
        urls.push(url);
      }
    }

    return urls;
  }

  function addQueryParam(url, key, value) {
    if (!value && value !== 0) {
      return url;
    }
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`;
  }

  async function fetchFirstReachable(urls, options) {
    let lastResponse = null;
    let lastError = null;

    for (const url of urls) {
      try {
        const response = await fetch(url, options);
        if (response.status === 404) {
          lastResponse = response;
          continue;
        }
        return { response, url };
      } catch (err) {
        lastError = err;
      }
    }

    if (lastError) {
      throw lastError;
    }
    return { response: lastResponse, url: "" };
  }

  function toStreamUrl(eventsUrl) {
    if (!eventsUrl) {
      return "";
    }
    if (eventsUrl.includes("/api/monitor/stream") || eventsUrl.includes("/monitor/stream")) {
      return eventsUrl;
    }
    if (eventsUrl.includes("/api/monitor/events")) {
      return eventsUrl.replace("/api/monitor/events", "/api/monitor/stream");
    }
    return eventsUrl.replace("/monitor/events", "/monitor/stream");
  }

  function clearStreamRetryTimer() {
    if (state.streamRetryTimer) {
      clearTimeout(state.streamRetryTimer);
      state.streamRetryTimer = null;
    }
  }

  function isMobileViewport() {
    return mobileViewport.matches;
  }

  function syncMobileLayout() {
    if (!isMobileViewport()) {
      body.classList.remove("mobile-chat-open");
      if (backToContactsBtn) {
        backToContactsBtn.classList.add("hidden");
      }
      return;
    }

    const chatOpen = state.mobileView === "chat" && Boolean(state.selectedPeer);
    body.classList.toggle("mobile-chat-open", chatOpen);
    if (backToContactsBtn) {
      backToContactsBtn.classList.toggle("hidden", !chatOpen);
    }
  }

  function showContactsView() {
    state.mobileView = "contacts";
    syncMobileLayout();
  }

  function showChatView() {
    if (!state.selectedPeer) {
      state.mobileView = "contacts";
    } else {
      state.mobileView = "chat";
    }
    syncMobileLayout();
  }


  function stopStream() {
    clearStreamRetryTimer();
    if (state.stream) {
      state.stream.close();
      state.stream = null;
    }
  }

  function scheduleStreamReconnect(delayMs = 3500) {
    if (state.streamRetryTimer) {
      return;
    }
    state.streamRetryTimer = setTimeout(() => {
      state.streamRetryTimer = null;
      connectStream();
    }, delayMs);
  }

  function connectStream(preferredEventsUrl = "") {
    stopStream();

    const streamUrls = [];
    const seen = new Set();

    function addStream(url) {
      if (!url) {
        return;
      }
      if (seen.has(url)) {
        return;
      }
      seen.add(url);
      streamUrls.push(url);
    }

    for (const url of composeCandidateUrls("stream")) {
      addStream(url);
    }
    if (preferredEventsUrl) {
      addStream(toStreamUrl(preferredEventsUrl));
    }
    for (const url of composeCandidateUrls("events")) {
      addStream(toStreamUrl(url));
    }

    if (streamUrls.length === 0) {
      scheduleStreamReconnect(pollSeconds * 1000);
      return;
    }

    let index = 0;
    const tryNext = () => {
      if (index >= streamUrls.length) {
        scheduleStreamReconnect(pollSeconds * 1000);
        return;
      }

      const url = streamUrls[index++];
      const source = new EventSource(url);
      let opened = false;

      const timeout = setTimeout(() => {
        if (!opened) {
          source.close();
          tryNext();
        }
      }, 4500);

      source.onopen = () => {
        opened = true;
        clearTimeout(timeout);
        state.stream = source;
      };

      source.addEventListener("monitor_update", async (event) => {
        try {
          const payload = JSON.parse(event.data || "{}");
          const incomingVersion = Number(payload.version || 0);
          if (incomingVersion && incomingVersion <= state.version) {
            return;
          }
        } catch {
          // si hay cualquier payload inesperado, igual recargamos.
        }
        await loadEvents({ silent: true, sinceVersion: state.version, incremental: true });
      });

      source.onerror = () => {
        clearTimeout(timeout);
        source.close();
        if (!opened) {
          tryNext();
          return;
        }
        state.stream = null;
        scheduleStreamReconnect(2500);
      };
    };

    tryNext();
  }

  function setPausedUI(paused) {
    state.paused = paused;
    statusBadge.textContent = paused ? "PAUSADO" : "ACTIVO";
    statusBadge.classList.toggle("chip-paused", paused);
    statusBadge.classList.toggle("chip-live", !paused);
    toggleBtn.textContent = paused ? "Reanudar bot" : "Pausar bot";
    toggleBtn.classList.toggle("btn-success", paused);
    toggleBtn.classList.toggle("btn-danger", !paused);
  }

  function normalizePeer(event) {
    if (!event.peer || event.peer === "-") {
      return "Sistema";
    }
    return event.peer;
  }

  function getPreview(event) {
    return event.body || event.detail || event.event_type || "(sin contenido)";
  }

  function getEventsForPeer(peer) {
    if (!peer) {
      return [];
    }
    if (state.conversationByPeer[peer]) {
      return state.conversationByPeer[peer];
    }
    return state.allEvents.filter((event) => normalizePeer(event) === peer);
  }

  function parseMonitorTimestamp(ts) {
    if (!ts) {
      return null;
    }

    const raw = String(ts).trim();
    if (!raw) {
      return null;
    }

    // Epoch (segundos o milisegundos)
    if (/^\d+$/.test(raw)) {
      const numeric = Number(raw);
      const millis = numeric > 1000000000000 ? numeric : numeric * 1000;
      const date = new Date(millis);
      return Number.isNaN(date.getTime()) ? null : date;
    }

    // Backend guarda "%Y-%m-%d %H:%M:%S" en UTC.
    const normalized = raw.replace(" ", "T");
    const looksLikeNaiveUtc = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(normalized);
    const date = new Date(looksLikeNaiveUtc ? `${normalized}Z` : normalized);
    return Number.isNaN(date.getTime()) ? null : date;
  }

  function formatClock(ts, { includeSeconds = false } = {}) {
    const raw = ts ? String(ts).trim() : "";
    const date = parseMonitorTimestamp(ts);
    if (!date) {
      return raw || "--:--";
    }

    return date.toLocaleTimeString(
      [],
      includeSeconds
        ? { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }
        : { hour: "2-digit", minute: "2-digit", hour12: false },
    );
  }

  function formatFullTimestamp(ts) {
    const raw = ts ? String(ts).trim() : "";
    const date = parseMonitorTimestamp(ts);
    if (!date) {
      return raw;
    }
    return date.toLocaleString([], {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }

  function formatHeaderStamp(ts) {
    const raw = ts ? String(ts).trim() : "";
    const date = parseMonitorTimestamp(ts);
    if (!date) {
      return raw || "--:--";
    }
    const day = date.toLocaleDateString([], { day: "2-digit", month: "short" });
    const time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
    return `${day} · ${time}`;
  }

  function dayKeyFromTimestamp(ts) {
    const date = parseMonitorTimestamp(ts);
    if (!date) {
      return "";
    }
    const year = String(date.getFullYear());
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function dayLabelFromTimestamp(ts) {
    const raw = ts ? String(ts).trim() : "";
    const date = parseMonitorTimestamp(ts);
    if (!date) {
      return raw;
    }
    return date.toLocaleDateString([], { year: "numeric", month: "long", day: "2-digit" });
  }

  function buildDaySeparator(ts) {
    const row = document.createElement("div");
    row.className = "day-separator";

    const chip = document.createElement("span");
    chip.className = "day-separator-chip";
    chip.textContent = dayLabelFromTimestamp(ts);

    row.appendChild(chip);
    return row;
  }

  function groupContacts(events) {
    const map = new Map();
    events.forEach((event, index) => {
      const peer = normalizePeer(event);
      if (!map.has(peer)) {
        map.set(peer, { peer, events: [], lastIndex: index });
      }
      const contact = map.get(peer);
      contact.events.push(event);
      contact.lastIndex = index;
    });

    const contacts = Array.from(map.values()).sort((a, b) => b.lastIndex - a.lastIndex);
    contacts.forEach((contact) => {
      contact.lastEvent = contact.events[contact.events.length - 1];
      contact.preview = getPreview(contact.lastEvent);
      contact.count = contact.events.length;
    });
    return contacts;
  }

  function createContactItem(contact) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `contact-item ${state.selectedPeer === contact.peer ? "active" : ""}`;
    btn.dataset.peer = contact.peer;

    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = (contact.peer || "?").slice(-2).toUpperCase();

    const main = document.createElement("div");
    main.className = "contact-main";

    const top = document.createElement("div");
    top.className = "contact-top";

    const name = document.createElement("span");
    name.className = "contact-name";
    name.textContent = contact.peer;

    const time = document.createElement("span");
    time.className = "contact-time";
    time.textContent = formatClock(contact.lastEvent?.ts);

    top.appendChild(name);
    top.appendChild(time);

    const preview = document.createElement("div");
    preview.className = "contact-preview";
    preview.textContent = contact.preview;

    main.appendChild(top);
    main.appendChild(preview);

    btn.appendChild(avatar);
    btn.appendChild(main);
    return btn;
  }

  function renderContacts(contacts) {
    contactsList.innerHTML = "";
    contacts.forEach((contact) => {
      contactsList.appendChild(createContactItem(contact));
    });
    contactsMeta.textContent = `${contacts.length} chats`;
    contactsEmpty.classList.toggle("hidden", contacts.length > 0);
    contactCount.textContent = String(contacts.length);
  }

  function buildMessageNode(event) {
    const messageClass =
      event.direction === "inbound"
        ? "inbound"
        : event.direction === "outbound"
          ? "outbound"
          : "system";

    const row = document.createElement("article");
    row.className = `msg ${messageClass}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";

    const bodyText = document.createElement("div");
    bodyText.className = "msg-body";
    bodyText.textContent = event.body || event.detail || "(sin contenido)";

    bubble.appendChild(bodyText);

    const time = document.createElement("div");
    time.className = "msg-time";
    time.textContent = formatClock(event.ts, { includeSeconds: true });
    time.title = formatFullTimestamp(event.ts);
    bubble.appendChild(time);

    row.appendChild(bubble);
    return row;
  }

  function syncExportChatButton(peer) {
    if (!exportChatBtn) {
      return;
    }
    exportChatBtn.disabled = !peer;
  }

  function renderConversation(peer) {
    chatTimeline.innerHTML = "";
    syncExportChatButton(peer);
    if (!peer) {
      activeContact.textContent = "Sin contacto seleccionado";
      activeMeta.textContent = "Selecciona un chat para ver el historial.";
      chatEmpty.classList.remove("hidden");
      showContactsView();
      return;
    }

    const events = getEventsForPeer(peer);
    const lastEvent = events.length ? events[events.length - 1] : null;

    activeContact.textContent = peer;
    activeMeta.textContent = `Último: ${formatHeaderStamp(lastEvent?.ts)}`;

    let lastDayKey = "";
    events.forEach((event) => {
      const dayKey = dayKeyFromTimestamp(event.ts);
      if (dayKey && dayKey !== lastDayKey) {
        chatTimeline.appendChild(buildDaySeparator(event.ts));
        lastDayKey = dayKey;
      }
      chatTimeline.appendChild(buildMessageNode(event));
    });
    chatEmpty.classList.toggle("hidden", events.length > 0);
    chatTimeline.scrollTop = chatTimeline.scrollHeight;
  }

  function renderAll(events) {
    const contacts = groupContacts(events || []);
    state.contacts = contacts;

    if (!state.selectedPeer || !contacts.some((c) => c.peer === state.selectedPeer)) {
      state.selectedPeer = contacts[0]?.peer || null;
    }

    renderContacts(contacts);
    renderConversation(state.selectedPeer);
    syncMobileLayout();
    eventCount.textContent = String(state.totalEvents || events.length);

    if (state.selectedPeer && !state.conversationByPeer[state.selectedPeer]) {
      loadPeerConversation(state.selectedPeer, { silent: true }).catch(() => {});
    }
  }

  function showError(message) {
    errorState.textContent = message;
    errorState.classList.remove("hidden");
  }

  function hideError() {
    errorState.classList.add("hidden");
    errorState.textContent = "";
  }

  async function loadPeerConversation(peer, { force = false, silent = false } = {}) {
    if (!peer) {
      return [];
    }

    if (!force && state.conversationByPeer[peer]) {
      return state.conversationByPeer[peer];
    }

    let urls = composeCandidateUrls("events");
    urls = urls.map((url) => addQueryParam(url, "peer", peer));

    try {
      const result = await fetchFirstReachable(urls, {
        headers: { Accept: "application/json" },
      });
      const resp = result.response;

      if (!resp || !resp.ok) {
        if (!silent) {
          const status = resp ? resp.status : "N/A";
          showError(`No se pudo cargar la conversacion de ${peer} (HTTP ${status}).`);
        }
        return [];
      }

      const data = await resp.json();
      if (!data.ok) {
        if (!silent) {
          showError(`El backend no devolvio datos para ${peer}.`);
        }
        return [];
      }

      state.conversationByPeer[peer] = data.events || [];
      if (state.selectedPeer === peer) {
        renderConversation(peer);
      }
      return state.conversationByPeer[peer];
    } catch (err) {
      if (!silent) {
        showError(`Error cargando conversacion de ${peer}: ${err.message || err}`);
      }
      return [];
    }
  }

  async function loadEvents({ silent = false, sinceVersion = 0, incremental = false } = {}) {
    let urls = composeCandidateUrls("events");
    if (sinceVersion > 0) {
      urls = urls.map((url) => addQueryParam(url, "since", sinceVersion));
    }
    try {
      const result = await fetchFirstReachable(urls, {
        headers: { Accept: "application/json" },
      });
      const resp = result.response;

      if (!resp) {
        if (!silent) {
          showError("No se pudo contactar el backend de monitoreo.");
        }
        return;
      }

      if (!resp.ok) {
        if (!silent) {
          if (resp.status === 404) {
            showError("No se encontro monitor/events. Abre /monitor desde Flask o usa ?api=http://localhost:8000");
          } else {
            showError(`No se pudo cargar monitor/events (HTTP ${resp.status}).`);
          }
        }
        return;
      }

      const data = await resp.json();
      if (!data.ok) {
        if (!silent) {
          showError("El backend de monitoreo devolvio un error.");
        }
        return;
      }

      hideError();
      const incomingEvents = data.events || [];
      const incomingTotal = Number(data.total || 0);
      if (incremental && sinceVersion > 0) {
        const delta = incomingEvents;
        if (delta.length > 0) {
          state.allEvents = state.allEvents.concat(delta);
          for (const ev of delta) {
            const peer = normalizePeer(ev);
            if (state.conversationByPeer[peer]) {
              const cached = state.conversationByPeer[peer];
              const exists = cached.some((item) => Number(item.version || 0) === Number(ev.version || -1));
              if (!exists) {
                cached.push(ev);
              }
            }
          }
        }
      } else {
        if (incomingTotal > 0 && incomingEvents.length === 0 && state.allEvents.length > 0) {
          // Evita "parpadear" a vacio si llega una respuesta inconsistente.
          if (!silent) {
            showError("Respuesta vacia del monitor; conservando historial local.");
          }
        } else {
          state.allEvents = incomingEvents;
        }
        state.conversationByPeer = {};
      }

      state.totalEvents = incomingTotal || state.allEvents.length || 0;
      renderAll(state.allEvents);
      setPausedUI(Boolean(data.paused));
      state.version = Number(data.version || state.version || 0);
      lastUpdate.textContent = `Ultima actualizacion: ${new Date().toLocaleTimeString()}`;
      persistCachedState();

      if (!state.stream) {
        connectStream(result.url);
      }
    } catch (err) {
      if (!silent) {
        showError(`Error de red consultando monitor/events: ${err.message || err}`);
      }
    }
  }

  async function togglePause() {
    const action = state.paused ? "resume" : "pause";
    const urls = composeCandidateUrls("pause");
    toggleBtn.disabled = true;
    try {
      const result = await fetchFirstReachable(urls, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify({ action }),
      });
      const resp = result.response;

      if (!resp) {
        showError("No se pudo contactar el backend para pausar/reanudar.");
        return;
      }

      if (!resp.ok) {
        showError(`No se pudo cambiar estado del bot (HTTP ${resp.status}).`);
        return;
      }

      const data = await resp.json();
      if (!data.ok) {
        showError("No se pudo cambiar el estado del bot.");
        return;
      }

      hideError();
      setPausedUI(Boolean(data.paused));
      await loadEvents({ silent: true, sinceVersion: state.version, incremental: true });
    } catch (err) {
      showError(`Error de red al pausar/reanudar: ${err.message || err}`);
    } finally {
      toggleBtn.disabled = false;
    }
  }

  function downloadContactsExcel() {
    const urls = composeCandidateUrls("export");
    if (!urls.length) {
      showError("No encontre una ruta de exportacion disponible.");
      return;
    }

    hideError();
    window.location.assign(urls[0]);
  }

  function downloadSelectedChatExcel() {
    if (!state.selectedPeer) {
      showError("Selecciona un chat para exportar.");
      return;
    }

    const urls = composeCandidateUrls("export_chat");
    if (!urls.length) {
      showError("No encontre una ruta de exportacion de chat disponible.");
      return;
    }

    hideError();
    window.location.assign(addQueryParam(urls[0], "peer", state.selectedPeer));
  }

  contactsList.addEventListener("click", (event) => {
    const item = event.target.closest(".contact-item");
    if (!item) {
      return;
    }
    state.selectedPeer = item.dataset.peer;
    renderContacts(state.contacts);
    renderConversation(state.selectedPeer);
    showChatView();
    loadPeerConversation(state.selectedPeer, { force: false, silent: true }).catch(() => {});
  });

  if (exportBtn) {
    exportBtn.addEventListener("click", downloadContactsExcel);
  }
  if (exportChatBtn) {
    exportChatBtn.addEventListener("click", downloadSelectedChatExcel);
  }
  if (backToContactsBtn) {
    backToContactsBtn.addEventListener("click", showContactsView);
  }
  if (mobileViewport.addEventListener) {
    mobileViewport.addEventListener("change", syncMobileLayout);
  } else if (mobileViewport.addListener) {
    mobileViewport.addListener(syncMobileLayout);
  }
  toggleBtn.addEventListener("click", togglePause);
  refreshBtn.addEventListener("click", () => loadEvents());
  window.addEventListener("beforeunload", stopStream);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      loadEvents({ silent: true });
    }
  });

  syncMobileLayout();
  loadCachedState();
  loadEvents();
})();
