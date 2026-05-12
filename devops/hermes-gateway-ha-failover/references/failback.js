#!/usr/bin/env node
/**
 * Gateway HA: Manual Failback
 * Run this when local machine is back online to resume MASTER role.
 */
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const CONFIG = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));
const STATE_FILE = path.join(__dirname, '.ha-state.json');

function shell(cmd, opts = {}) {
  try {
    return execSync(cmd, { encoding: 'utf8', stdio: opts.silent ? 'pipe' : 'inherit', ...opts });
  } catch (e) {
    if (opts.ignoreError) return '';
    throw e;
  }
}

function notify(title, msg) {
  if (!CONFIG.notification.enabled) return;
  try {
    execSync(`${CONFIG.notification.command} "${title}" "${msg}"`, { stdio: 'ignore' });
  } catch {}
}

function loadState() {
  try { return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')); }
  catch { return { mode: 'MASTER' }; }
}

function saveState(s) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(s, null, 2));
}

console.log('[FAILBACK] Step 1/3: Stopping remote gateway...');
try {
  shell(`ssh -p ${CONFIG.remote.ssh_port} ${CONFIG.remote.host} "systemctl --user stop ${CONFIG.remote.gateway_service}"`, { silent: true });
  console.log('[FAILBACK] Remote gateway stopped.');
} catch (e) {
  console.warn('[FAILBACK] Could not stop remote (may already be stopped):', e.message);
}

console.log(`[FAILBACK] Step 2/3: Waiting ${CONFIG.remote.ilink_timeout_sec} seconds for iLink session release...`);
shell(`sleep ${CONFIG.remote.ilink_timeout_sec}`, { silent: true });

console.log('[FAILBACK] Step 3/3: Starting local gateway...');
try {
  shell(`systemctl --user restart ${CONFIG.local.gateway_service}`, { silent: true });
  
  shell(`sleep 5`);
  const status = shell(`systemctl --user is-active ${CONFIG.local.gateway_service}`, { silent: true, ignoreError: true }).trim();
  if (status === 'active') {
    const state = loadState();
    state.mode = 'MASTER';
    state.failCount = 0;
    state.lastFailback = Date.now();
    saveState(state);
    notify('Gateway FAILBACK', 'Local gateway restored. You are now MASTER.');
    console.log('[FAILBACK] Success. Local gateway is active.');
  } else {
    throw new Error('Local gateway did not reach active state');
  }
} catch (e) {
  console.error('[FAILBACK] Failed:', e.message);
  notify('Gateway ERROR', `Failback failed: ${e.message}`);
  process.exit(1);
}
