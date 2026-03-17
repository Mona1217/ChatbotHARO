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
  const toggleBtn = document.getElementById("togglePauseBtn");
  const refreshBtn = document.getElementById("refreshBtn");
  const activeContact = document.getElementById("activeContact");
  const activeMeta = document.getElementById("activeMeta");

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
  };

  function withToken(url) {
    if (!token) {
      return url;
    }
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}token=${encodeURIComponent(token)}`;
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

    if (!explicitApiBase && protocol.startsWith("http") && hostname && port !== "8000") {
      add(`${protocol}//${hostname}:8000`);
    }

    add("http://127.0.0.1:8000");
    add("http://localhost:8000");
    add("");

    return candidates;
  }

  function getEndpointCandidates(kind) {
    const candidates = [];
    const seen = new Set();
    const path = window.location.pathname.replace(/\/+$/, "");

    function add(rawPath) {
      const normalized = rawPath.startsWith("/") ? rawPath : `/${rawPath}`;
      if (seen.has(normalized)) {
        return;
      }
      seen.add(normalized);
      candidates.push(normalized);
    }

    add(`/monitor/${kind}`);
    add(`/api/monitor/${kind}`);

    if (path.endsWith("/monitor")) {
      const base = path.slice(0, -"/monitor".length);
      add(`${base}/monitor/${kind}`);
      add(`${base}/api/monitor/${kind}`);
    }

    if (path.endsWith("/static/monitor.html")) {
      const base = path.slice(0, -"/static/monitor.html".length);
      add(`${base}/monitor/${kind}`);
      add(`${base}/api/monitor/${kind}`);
    }

    return candidates;
  }

  function composeCandidateUrls(kind) {
    const bases = getApiBaseCandidates();
    const paths = getEndpointCandidates(kind);
    const urls = [];
    const seen = new Set();

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

    const eventUrls = composeCandidateUrls("events");
    const streamUrls = [];
    const seen = new Set();

    function addStream(url) {
      if (!url) {
        return;
      }
      const streamUrl = toStreamUrl(url);
      if (!streamUrl || seen.has(streamUrl)) {
        return;
      }
      seen.add(streamUrl);
      streamUrls.push(streamUrl);
    }

    if (preferredEventsUrl) {
      addStream(preferredEventsUrl);
    }
    for (const url of eventUrls) {
      addStream(url);
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

  function formatClock(ts) {
    if (!ts) {
      return "--:--";
    }
    const date = new Date(ts.replace(" ", "T"));
    if (Number.isNaN(date.getTime())) {
      return ts;
    }
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
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
    time.textContent = formatClock(event.ts);
    bubble.appendChild(time);

    row.appendChild(bubble);
    return row;
  }

  function renderConversation(peer) {
    chatTimeline.innerHTML = "";
    if (!peer) {
      activeContact.textContent = "Sin contacto seleccionado";
      activeMeta.textContent = "Selecciona un chat para ver el historial.";
      chatEmpty.classList.remove("hidden");
      return;
    }

    const events = getEventsForPeer(peer);
    const lastEvent = events.length ? events[events.length - 1] : null;

    activeContact.textContent = peer;
    activeMeta.textContent = `ultimo ${formatClock(lastEvent?.ts)}`;
    events.forEach((event) => {
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
      if (incremental && sinceVersion > 0) {
        const delta = data.events || [];
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
        state.allEvents = data.events || [];
        state.conversationByPeer = {};
      }

      state.totalEvents = Number(data.total || state.allEvents.length || 0);
      renderAll(state.allEvents);
      setPausedUI(Boolean(data.paused));
      state.version = Number(data.version || state.version || 0);
      lastUpdate.textContent = `Ultima actualizacion: ${new Date().toLocaleTimeString()}`;

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

  contactsList.addEventListener("click", (event) => {
    const item = event.target.closest(".contact-item");
    if (!item) {
      return;
    }
    state.selectedPeer = item.dataset.peer;
    renderContacts(state.contacts);
    renderConversation(state.selectedPeer);
    loadPeerConversation(state.selectedPeer, { force: false, silent: true }).catch(() => {});
  });

  toggleBtn.addEventListener("click", togglePause);
  refreshBtn.addEventListener("click", () => loadEvents());
  window.addEventListener("beforeunload", stopStream);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      loadEvents({ silent: true });
    }
  });

  loadEvents();
})();
