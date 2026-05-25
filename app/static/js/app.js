const API = "/api/v1";

const PROP_KEYS = [
  "motd", "difficulty", "gamemode", "max-players", "pvp", "online-mode",
  "enable-command-block", "spawn-protection", "view-distance", "simulation-distance",
  "allow-flight", "white-list", "hardcore", "level-seed",
];

let consoleWs = null;
let statusPoll = null;
let networkPoll = null;
let propsCache = {};
let currentUser = null;
let userServers = [];
let currentPlanId = "free";
let currentPlan = getPlan(currentPlanId);
let currentProfile = null;
let activeServerId = null;

const PLUS_NOT_AVAILABLE_MESSAGE = "OpenHome Plus is planned, but not available yet.";

const $ = (id) => document.getElementById(id);
const page = document.body.dataset.page || "home";
const hasSupabase = () => typeof supabaseClient !== "undefined" && Boolean(supabaseClient?.auth);

function toast(message, type = "success") {
  const el = $("toast");
  if (!el) return;
  el.textContent = message;
  el.className = `toast ${type}`;
  el.style.display = "block";
  window.clearTimeout(el._timer);
  el._timer = window.setTimeout(() => { el.style.display = "none"; }, 4200);
}

function escapeHtml(value = "") {
  return String(value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function displayName(user) {
  if (!user) return "Account";
  return user.user_metadata?.name || user.email || "Account";
}

function normalizePlanForUi(planData) {
  if (!planData) return getPlan("free");
  return {
    id: planData.id || "free",
    name: planData.name || "OpenHome Free",
    tagline: getPlan(planData.id || "free").tagline,
    maxServers: Number(planData.max_servers ?? 1),
    ramMb: Number(planData.ram_mb ?? 1024),
    storageGb: Number(planData.storage_gb ?? 2),
    maxPlayers: Number(planData.max_players ?? 10),
    autoStopMinutes: Number(planData.auto_stop_minutes ?? 10),
    allowPlugins: Boolean(planData.allow_plugins),
    allowWorldUpload: Boolean(planData.allow_world_upload),
    allowBackups: Boolean(planData.allow_backups),
    allowCustomDomain: Boolean(planData.allow_custom_domain),
    priorityStartup: Boolean(planData.priority_startup),
    adminControlled: Boolean(planData.admin_controlled),
    available: Boolean(planData.available),
  };
}

function getCurrentPlan() {
  return currentPlan || getPlan(currentPlanId);
}

function displayPlanName(planValue) {
  const normalized = String(planValue || "").trim().toLowerCase();
  if (normalized === "plus") return "OpenHome Plus";
  if (normalized === "free") return "OpenHome Free";
  return planValue || "OpenHome Free";
}

async function getSession() {
  if (!hasSupabase()) return null;
  const { data, error } = await supabaseClient.auth.getSession();
  return error ? null : data.session || null;
}

async function getVerifiedUser() {
  if (!hasSupabase()) return null;
  const { data, error } = await supabaseClient.auth.getUser();
  return (error || !data?.user) ? null : data.user;
}

async function requireAuth() {
  currentUser = await getVerifiedUser();
  if (!currentUser) {
    window.location.href = "./login.html";
    return null;
  }
  return currentUser;
}

async function getAccessToken() {
  const session = await getSession();
  return session?.access_token || null;
}

async function api(path, options = {}) {
  const opts = { ...options };
  opts.headers = { ...(options.headers || {}) };
  const token = await getAccessToken();
  if (token) opts.headers.Authorization = `Bearer ${token}`;
  if (opts.body && !(opts.body instanceof FormData)) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(opts.body);
  }
  const response = await fetch(`${API}${path}`, opts);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status}: ${text || response.statusText}`);
  }
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) return null;
  return response.json();
}

async function loadCurrentProfile(showErrors = true) {
  if (!hasSupabase()) return null;
  try {
    currentProfile = await api("/profile/");
    currentPlanId = currentProfile?.plan || "free";
    currentPlan = normalizePlanForUi(currentProfile?.limits);
    return currentProfile;
  } catch (error) {
    currentProfile = null;
    currentPlanId = "free";
    currentPlan = getPlan("free");
    if (showErrors) toast(`Could not load profile: ${error.message}`, "error");
    return null;
  }
}

function initNav() {
  const activePage = page === "server-detail" ? "servers" : page;
  document.querySelectorAll("[data-page-link]").forEach((link) => {
    link.classList.toggle("active", link.dataset.pageLink === activePage);
  });
  const toggle = $("nav-toggle");
  const nav = $("main-nav");
  if (toggle && nav) {
    toggle.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
  }
}

async function updateAuthNav() {
  const session = await getSession();
  const user = session?.user || null;

  document.querySelectorAll("[data-auth-link]").forEach((link) => {
    const type = link.dataset.authLink;
    link.onclick = null;

    if (user && type === "login") {
      link.textContent = "Log out";
      link.setAttribute("href", "#logout");
      link.onclick = async (event) => {
        event.preventDefault();
        await supabaseClient.auth.signOut();
        currentUser = null;
        userServers = [];
        toast("Signed out");
        window.location.href = "./index.html";
      };
    } else if (user && type === "register") {
      link.textContent = displayName(user);
      link.setAttribute("href", "./servers.html");
    } else if (!user && type === "login") {
      link.textContent = "Log in";
      link.setAttribute("href", "./login.html");
    } else if (!user && type === "register") {
      link.textContent = "Register";
      link.setAttribute("href", "./register.html");
    }
  });
}

function initPlusCtas() {
  document.querySelectorAll("[data-plus-cta]").forEach((element) => {
    element.addEventListener("click", (event) => {
      const href = element.getAttribute("href");
      const shouldNavigate = element.dataset.plusCta === "navigate" && href;
      event.preventDefault();
      toast(PLUS_NOT_AVAILABLE_MESSAGE, "error");
      if (shouldNavigate) {
        window.setTimeout(() => {
          window.location.href = href;
        }, 250);
      }
    });
  });
}

function initAuthForms() {
  const loginForm = $("login-form");
  if (loginForm) {
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!hasSupabase()) { toast("Supabase not loaded.", "error"); return; }
      const email = $("login-email").value.trim().toLowerCase();
      const password = $("login-password").value;
      const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
      if (error) { toast(error.message, "error"); return; }
      toast("Session started");
      window.location.href = "./servers.html";
    });
  }

  const registerForm = $("register-form");
  if (registerForm) {
    registerForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!hasSupabase()) { toast("Supabase not loaded.", "error"); return; }
      const name = $("register-name").value.trim();
      const email = $("register-email").value.trim().toLowerCase();
      const password = $("register-password").value;

      const { data, error } = await supabaseClient.auth.signUp({
        email, password,
        options: { data: { name } },
      });
      if (error) { toast(error.message, "error"); return; }

      if (data.session) {
        currentUser = data.user;
        toast("Account created. Welcome!", "success");
        window.location.href = "./servers.html";
        return;
      }

      window.location.href = "./auth-confirm.html";
    });
  }
}

async function loadServers(showErrors = true) {
  if (!hasSupabase()) return [];
  try {
    userServers = await api("/servers/");
    return userServers;
  } catch (error) {
    if (showErrors) toast(`Could not load servers: ${error.message}`, "error");
    userServers = [];
    return [];
  }
}

async function createServerRecord(name, showToast = true) {
  const user = currentUser || await getVerifiedUser();
  if (!user) { window.location.href = "./login.html"; return null; }

  const plan = getCurrentPlan();
  if (!canCreateServer(userServers, currentPlanId)) {
    toast(`${plan.name} allows up to ${plan.maxServers} server. Delete one server before creating another.`, "error");
    return null;
  }

  try {
    const server = await api("/servers/", {
      method: "POST",
      body: {
        name,
        description: "Server created from OpenHome.",
        minecraft_version: "latest",
        loader: "paper",
      },
    });
    await loadServers(false);
    if (showToast) toast("Server created");
    return server;
  } catch (error) {
    toast(`Creation failed: ${error.message}`, "error");
    return null;
  }
}

function renderPlanBanner() {
  const banner = $("plan-banner");
  if (!banner) return;
  const plan = getCurrentPlan();
  if ($("plan-badge")) $("plan-badge").textContent = plan.name;
  if ($("servers-used")) $("servers-used").textContent = userServers.length;
  if ($("servers-max")) $("servers-max").textContent = plan.maxServers;
  if ($("ram-limit")) $("ram-limit").textContent = formatRam(plan.ramMb);
  if ($("storage-limit")) $("storage-limit").textContent = `${plan.storageGb} GB`;
  if ($("auto-stop")) $("auto-stop").textContent = `${plan.autoStopMinutes} min`;
}

function renderServersGrid() {
  const grid = $("servers-grid");
  if (!grid) return;

  const plan = getCurrentPlan();
  const canCreate = canCreateServer(userServers, currentPlanId);

  let cards = "";

  if (userServers.length === 0) {
    cards = `
      <article class="server-card">
        <div class="empty-state">
          <div>
            <span class="kicker">No servers</span>
            <h3>No servers yet</h3>
            <p class="muted">Create your first free Minecraft server.</p>
            <div class="separator"></div>
            <button class="primary" type="button" onclick="handleCreateServer()" ${canCreate ? "" : "disabled"}>
              ${canCreate ? "Create server" : "Server limit reached"}
            </button>
          </div>
        </div>
      </article>
    `;
  } else {
    for (const server of userServers) {
      const ramGb = Number(server.ram_mb || 1024) >= 1024
        ? `${Math.round(Number(server.ram_mb || 1024) / 1024)} GB`
        : `${server.ram_mb} MB`;

      cards += `
        <article class="server-card">
          <div class="server-top">
            <div>
              <span class="kicker">${escapeHtml(displayPlanName(server.plan))}</span>
              <h3>${escapeHtml(server.name)}</h3>
              <p class="muted">${escapeHtml(server.description || "")}</p>
            </div>
            <div class="server-icon">MC</div>
          </div>
          <span class="status-badge status-${escapeHtml(server.status || "created")}">${escapeHtml(server.status || "created")}</span>
          <div class="server-specs">
            <div class="spec"><strong>${escapeHtml(ramGb)}</strong><span>RAM</span></div>
            <div class="spec"><strong>${escapeHtml(server.max_players || 10)}</strong><span>Players</span></div>
            <div class="spec"><strong>${escapeHtml(server.loader || "paper")}</strong><span>Loader</span></div>
            <div class="spec"><strong>${escapeHtml(server.minecraft_version || "latest")}</strong><span>Version</span></div>
          </div>
          <a class="button ghost" href="./server-detail.html?id=${escapeHtml(server.id)}">Manage</a>
        </article>
      `;
    }
  }

  grid.innerHTML = cards;
}

async function createAndStartServer() {
  const plan = getCurrentPlan();
  if (!canCreateServer(userServers, currentPlanId)) {
    toast(`${plan.name} allows up to ${plan.maxServers} server. Delete one server before creating another.`, "error");
    return;
  }

  const name = prompt("Server name:", `Survival CLT ${userServers.length + 1}`);
  if (!name || !name.trim()) return;

  const user = currentUser || await getVerifiedUser();
  if (!user) { window.location.href = "./login.html"; return; }

  const serverName = name.trim();
  toast("Creating server...", "success");

  const server = await createServerRecord(serverName, false);
  if (!server?.id) return;

  const serverId = server.id;
  toast("Server created. Provisioning...", "success");

  try {
    await api(`/servers/${serverId}/provision`, {
      method: "POST",
      body: { minecraft_version: "latest", loader: "paper" },
    });
    toast("Server provisioned. Starting...", "success");
  } catch (e) {
    toast(`Provision failed (backend may not be ready): ${e.message}`, "error");
    await loadServers(false);
    renderServersGrid();
    return;
  }

  try {
    await api(`/servers/${serverId}/start`, { method: "POST" });
    toast("Server started! Connecting...", "success");
  } catch (e) {
    toast(`Start failed: ${e.message}`, "error");
  }

  await loadServers(false);
  renderPlanBanner();
  renderServersGrid();
  window.location.href = `./server-detail.html?id=${serverId}`;
}

async function handleCreateServer() {
  const plan = getCurrentPlan();
  if (!canCreateServer(userServers, currentPlanId)) {
    toast(`${plan.name} allows up to ${plan.maxServers} server. Delete one server before creating another.`, "error");
    return;
  }
  const name = prompt("Server name:", `Survival CLT ${userServers.length + 1}`);
  if (name && name.trim()) {
    await createServerRecord(name.trim());
    renderPlanBanner();
    renderServersGrid();
  }
}

function setStatusUi(state = {}) {
  const value = state.status || "stopped";
  const badge = $("status-badge");
  if (badge) { badge.textContent = value; badge.className = `status-badge status-${value}`; }
  if ($("status-pid")) $("status-pid").textContent = state.pid ?? "—";
  if ($("status-players")) $("status-players").textContent = Array.isArray(state.players) ? state.players.length : "—";
  if ($("status-uptime")) $("status-uptime").textContent = state.uptime_seconds ? `${Math.floor(state.uptime_seconds / 60)}m` : "—";
  if ($("status-version")) $("status-version").textContent = state.version || "Minecraft";
}

async function refreshStatus() {
  try {
    const path = activeServerId
      ? `/servers/${activeServerId}/status`
      : "/instance/status";
    const state = await api(path);
    setStatusUi(state);
  } catch {
    setStatusUi({ status: "offline" });
  }
}

async function instanceAction(action) {
  if (activeServerId && action === "kill") {
    toast("Kill is not available for managed servers.", "error");
    return;
  }
  try {
    const path = activeServerId
      ? `/servers/${activeServerId}/${action}`
      : `/instance/${action}`;
    const body = !activeServerId && action === "start" ? { force: false } : {};
    const state = await api(path, { method: "POST", body });
    setStatusUi(state || {});
    toast(`Action sent: ${action}`);
  } catch (error) {
    toast(error.message, "error");
  }
}

async function loadProperties() {
  const form = $("properties-form");
  if (!form) return;
  try {
    propsCache = await api("/properties/");
    form.innerHTML = PROP_KEYS.map((key) => `
      <label>
        ${escapeHtml(key)}
        <input data-prop="${escapeHtml(key)}" value="${escapeHtml(propsCache[key] ?? "")}" placeholder="${escapeHtml(key)}" />
      </label>
    `).join("");
  } catch (error) {
    form.innerHTML = `<p class="muted">Could not read server.properties. ${escapeHtml(error.message)}</p>`;
  }
}

async function saveProperties() {
  const form = $("properties-form");
  if (!form) return;
  const next = { ...propsCache };
  form.querySelectorAll("[data-prop]").forEach((input) => { next[input.dataset.prop] = input.value; });
  try {
    propsCache = await api("/properties/", { method: "PUT", body: { properties: next } });
    toast("server.properties saved");
    await loadProperties();
  } catch (error) {
    toast(error.message, "error");
  }
}

function appendConsoleLine(text, type = "info") {
  const log = $("console-log");
  if (!log) return;
  if (log.textContent === "Waiting for console...") log.textContent = "";
  const line = document.createElement("div");
  line.className = `console-line ${type}`;
  line.textContent = text;
  log.appendChild(line);
  log.scrollTop = log.scrollHeight;
}

async function connectConsole() {
  if (!$("console-log")) return;
  const token = await getAccessToken();
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const query = token ? `?access_token=${encodeURIComponent(token)}` : "";
  const path = activeServerId
    ? `/api/v1/servers/${activeServerId}/console`
    : "/api/v1/ws/console";
  const url = `${scheme}://${location.host}${path}${query}`;
  const wsStatus = $("ws-status");

  try {
    consoleWs = new WebSocket(url);
  } catch (error) {
    if (wsStatus) wsStatus.textContent = "unavailable";
    appendConsoleLine(error.message, "error");
    return;
  }

  consoleWs.addEventListener("open", () => {
    if (wsStatus) wsStatus.textContent = "online";
    appendConsoleLine("WebSocket connected", "info");
  });
  consoleWs.addEventListener("message", (event) => {
    try {
      const msg = JSON.parse(event.data);
      appendConsoleLine(msg.data, msg.type === "error" ? "error" : "info");
    } catch { appendConsoleLine(event.data, "info"); }
  });
  consoleWs.addEventListener("close", () => { if (wsStatus) wsStatus.textContent = "offline"; });
  consoleWs.addEventListener("error", () => { if (wsStatus) wsStatus.textContent = "error"; });
}

function sendConsoleCommand(command) {
  if (!command) return;
  if (consoleWs && consoleWs.readyState === WebSocket.OPEN) {
    consoleWs.send(JSON.stringify({ type: "command", data: command }));
    appendConsoleLine(`> ${command}`, "info");
    return;
  }
  const path = activeServerId
    ? `/servers/${activeServerId}/command`
    : "/instance/console";
  api(path, { method: "POST", body: { command } })
    .then(() => appendConsoleLine(`> ${command}`, "info"))
    .catch((error) => toast(error.message, "error"));
}

async function refreshNetwork() {
  try {
    const [tunnel, dns] = await Promise.allSettled([
      api("/tunnel/status"),
      api("/tunnel/dns"),
    ]);
    if ($("tunnel-status")) {
      const t = tunnel.status === "fulfilled" ? (tunnel.value?.public_url || tunnel.value?.url || tunnel.value?.status || "configured") : "offline";
      $("tunnel-status").textContent = t;
    }
    if ($("dns-status")) {
      const d = dns.status === "fulfilled" ? (dns.value?.hostname || dns.value?.domain || dns.value?.status || "configured") : "offline";
      $("dns-status").textContent = d;
    }
  } catch {
    if ($("tunnel-status")) $("tunnel-status").textContent = "offline";
    if ($("dns-status")) $("dns-status").textContent = "offline";
  }
}

async function uploadPlugin() {
  const input = $("plugin-file");
  if (!input?.files?.length) { toast("Select a .jar file", "error"); return; }
  const data = new FormData();
  data.append("file", input.files[0]);
  try {
    const path = activeServerId ? `/servers/${activeServerId}/plugins` : "/assets/plugin";
    await api(path, { method: "POST", body: data });
    toast("Plugin uploaded");
  } catch (error) { toast(error.message, "error"); }
}

async function uploadWorld() {
  const input = $("world-file");
  if (!input?.files?.length) { toast("Select a .zip file", "error"); return; }
  const data = new FormData();
  data.append("file", input.files[0]);
  try {
    const path = activeServerId ? `/servers/${activeServerId}/world` : "/assets/world";
    await api(path, { method: "POST", body: data });
    toast("World uploaded");
  } catch (error) { toast(error.message, "error"); }
}

async function initServersPage() {
  const user = await requireAuth();
  if (!user) return;
  activeServerId = null;

  await loadCurrentProfile();
  renderPlanBanner();
  renderServersGrid();
  await loadServers();
  renderPlanBanner();
  renderServersGrid();

  refreshStatus();
  loadProperties();
  refreshNetwork();
  connectConsole();

  statusPoll = window.setInterval(refreshStatus, 5000);
  networkPoll = window.setInterval(refreshNetwork, 12000);

  $("create-server-btn")?.addEventListener("click", handleCreateServer);
  $("quickstart-btn")?.addEventListener("click", createAndStartServer);
  $("logout-button")?.addEventListener("click", async () => {
    await supabaseClient.auth.signOut();
    currentUser = null; userServers = [];
    toast("Signed out");
    window.location.href = "./index.html";
  });

  $("start-server")?.addEventListener("click", () => instanceAction("start"));
  $("stop-server")?.addEventListener("click", () => instanceAction("stop"));
  $("restart-server")?.addEventListener("click", () => instanceAction("restart"));
  $("kill-server")?.addEventListener("click", () => instanceAction("kill"));
  $("reload-properties")?.addEventListener("click", loadProperties);
  $("save-properties")?.addEventListener("click", saveProperties);

  $("console-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = $("console-command");
    sendConsoleCommand(input.value.trim());
    input.value = "";
  });

  $("start-tunnel")?.addEventListener("click", () =>
    api("/tunnel/start", { method: "POST" }).then(refreshNetwork).then(() => toast("Tunnel started")).catch((error) => toast(error.message, "error"))
  );
  $("stop-tunnel")?.addEventListener("click", () =>
    api("/tunnel/stop", { method: "POST" }).then(refreshNetwork).then(() => toast("Tunnel stopped")).catch((error) => toast(error.message, "error"))
  );
  $("update-dns")?.addEventListener("click", () =>
    api("/tunnel/dns/update", { method: "POST" }).then(refreshNetwork).then(() => toast("DNS updated")).catch((error) => toast(error.message, "error"))
  );

  $("upload-plugin")?.addEventListener("click", uploadPlugin);
  $("upload-world")?.addEventListener("click", uploadWorld);
}

async function initServerDetailPage() {
  const user = await requireAuth();
  if (!user) return;

  await loadCurrentProfile(false);

  const params = new URLSearchParams(window.location.search);
  const serverId = params.get("id");
  activeServerId = serverId;
  if (!serverId) {
    $("server-detail-name").textContent = "No server selected";
    $("server-detail-kicker").textContent = "Error";
    return;
  }

  $("server-detail-name").textContent = "Loading...";
  $("server-detail-kicker").textContent = `Server`;

  try {
    const server = await api(`/servers/${serverId}`);
    $("server-detail-name").textContent = server.name;
    $("server-detail-kicker").textContent = `${displayPlanName(server.plan)} · ${server.loader}`;
    $("server-detail-meta").textContent = `${server.minecraft_version} · ${formatRam(server.ram_mb || 1024)} RAM`;
  } catch {
    $("server-detail-name").textContent = "Server not found";
    return;
  }

  refreshStatus();
  loadProperties();
  refreshNetwork();
  connectConsole();

  statusPoll = window.setInterval(refreshStatus, 5000);
  networkPoll = window.setInterval(refreshNetwork, 12000);

  $("start-server")?.addEventListener("click", () => instanceAction("start"));
  $("stop-server")?.addEventListener("click", () => instanceAction("stop"));
  $("restart-server")?.addEventListener("click", () => instanceAction("restart"));
  $("kill-server")?.addEventListener("click", () => instanceAction("kill"));
  $("reload-properties")?.addEventListener("click", loadProperties);
  $("save-properties")?.addEventListener("click", saveProperties);

  $("console-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = $("console-command");
    sendConsoleCommand(input.value.trim());
    input.value = "";
  });

  $("start-tunnel")?.addEventListener("click", () =>
    api("/tunnel/start", { method: "POST" }).then(refreshNetwork).then(() => toast("Tunnel started")).catch((error) => toast(error.message, "error"))
  );
  $("stop-tunnel")?.addEventListener("click", () =>
    api("/tunnel/stop", { method: "POST" }).then(refreshNetwork).then(() => toast("Tunnel stopped")).catch((error) => toast(error.message, "error"))
  );
  $("update-dns")?.addEventListener("click", () =>
    api("/tunnel/dns/update", { method: "POST" }).then(refreshNetwork).then(() => toast("DNS updated")).catch((error) => toast(error.message, "error"))
  );

  $("upload-plugin")?.addEventListener("click", uploadPlugin);
  $("upload-world")?.addEventListener("click", uploadWorld);
}

window.addEventListener("beforeunload", () => {
  if (statusPoll) window.clearInterval(statusPoll);
  if (networkPoll) window.clearInterval(networkPoll);
  if (consoleWs) consoleWs.close();
});

(async function boot() {
  initNav();
  initPlusCtas();
  await updateAuthNav();
  initAuthForms();

  const session = await getSession();
  if (session && (page === "login" || page === "register")) {
    window.location.href = "./servers.html";
    return;
  }

  if (page === "servers") await initServersPage();
  if (page === "server-detail") await initServerDetailPage();

  $("resend-confirm")?.addEventListener("click", async () => {
    if (!hasSupabase()) { toast("Supabase not loaded.", "error"); return; }
    const email = prompt("Enter your email address to resend confirmation:");
    if (!email || !email.trim()) return;
    const { error } = await supabaseClient.auth.resend({
      type: "signup",
      email: email.trim(),
    });
    if (error) { toast(error.message, "error"); return; }
    toast("Confirmation email resent.");
  });
})();
