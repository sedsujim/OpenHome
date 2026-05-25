// OpenHome Supabase client.
// This file intentionally contains only the publishable key.
// Never put the service_role / secret key in frontend code.
// If you publish the frontend on GitHub Pages, set OPENHOME_API_BASE
// to the origin of your deployed FastAPI backend.

const SUPABASE_URL = "https://kvuvkikzxthwybtjagml.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_9nwiOSoMDT2N8rxsCerytA_eLXfScO5";
const OPENHOME_API_BASE = "";

const DEFAULT_OPENHOME_API_BASE = ["localhost", "127.0.0.1"].includes(window.location.hostname)
  ? window.location.origin
  : "";

const OPENHOME_SITE_BASE = (() => {
  const url = new URL(window.location.href);
  const segments = url.pathname.split("/");
  segments.pop();
  url.pathname = `${segments.join("/")}/`;
  url.search = "";
  url.hash = "";
  return url.toString();
})();

window.OPENHOME_API_BASE = OPENHOME_API_BASE || DEFAULT_OPENHOME_API_BASE;
window.OPENHOME_SITE_BASE = OPENHOME_SITE_BASE;

const supabaseClient = window.supabase.createClient(
  SUPABASE_URL,
  SUPABASE_PUBLISHABLE_KEY
);
