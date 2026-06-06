/* ════════════════════════════════════════════════════════════════
   bk-auth.js — shared Supabase client (single source of auth config)
   ────────────────────────────────────────────────────────────────
   Loaded by every page that talks to Supabase (index, dashboard,
   reset-password, verify), AFTER the supabase-js CDN script and
   BEFORE any page script that uses `sb`. Declares the global `sb`
   client once so the config (URL + publishable key + client options)
   lives in exactly one place — rotate the key here and every page
   follows.
════════════════════════════════════════════════════════════════ */
const SUPABASE_URL = 'https://lteeroxgbxbgvfqntfoo.supabase.co';
const SUPABASE_KEY = 'sb_publishable_J2Ik8meti23EXo_sNEX7bQ_dpYmZDgz';
const sb = window.supabase.createClient(SUPABASE_URL, SUPABASE_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true }
});
