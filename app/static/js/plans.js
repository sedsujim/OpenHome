const FREE_PLAN = {
  id: "free",
  name: "OpenHome Free",
  tagline: "Free forever",
  maxServers: 1,
  ramMb: 1024,
  storageGb: 2,
  maxPlayers: 10,
  autoStopMinutes: 10,
  allowPlugins: true,
  allowWorldUpload: true,
  allowBackups: false,
  allowCustomDomain: false,
  priorityStartup: false,
  adminControlled: false,
  uptime: "Auto-stop enabled",
  status: "active",
  available: true,
};

const PLUS_PLAN = {
  id: "plus",
  name: "OpenHome Plus",
  tagline: "Planned",
  maxServers: 3,
  ramMb: 4096,
  storageGb: 10,
  maxPlayers: 25,
  autoStopMinutes: 120,
  allowPlugins: true,
  allowWorldUpload: true,
  allowBackups: true,
  allowCustomDomain: true,
  priorityStartup: true,
  adminControlled: true,
  uptime: "Longer uptime",
  status: "planned",
  available: false,
};

function getPlan(planId) {
  if (planId === "plus") return PLUS_PLAN;
  return FREE_PLAN;
}

function canCreateServer(servers, planId) {
  const plan = getPlan(planId);
  return servers.length < plan.maxServers;
}

function getServerLimit(planId) {
  return getPlan(planId).maxServers;
}

function formatRam(mb) {
  return mb >= 1024 ? `${Math.round(mb / 1024)} GB` : `${mb} MB`;
}
