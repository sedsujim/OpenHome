// OpenHome Supabase client.
// This file intentionally contains only the publishable key.
// Never put the service_role / secret key in frontend code.

const SUPABASE_URL = "https://kvuvkikzxthwybtjagml.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_9nwiOSoMDT2N8rxsCerytA_eLXfScO5";

const supabaseClient = window.supabase.createClient(
  SUPABASE_URL,
  SUPABASE_PUBLISHABLE_KEY
);
