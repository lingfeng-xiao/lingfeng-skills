#!/usr/bin/env node
/**
 * Gateway HA: Local Health Monitor
 * Detects local gateway failure and triggers remote failover.
 * Single-account cold-switch (Route B).
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
  catch { return { mode: 'MASTER', failCount: 0, lastCheck: 0, lastFailover: 0 }; }
}

function saveState(s) {
  fs.writeFileSync(STATE_FILE, JSON.stringify(s, null, 2));
}

function isGatewayActive() {
  try {
    const out = shell(`systemctl --user is-active ${CONFIG.local.gateway_service}`, { silent: true, ignoreError: true }).trim();
    return out === 'active';
  } catch { return false; }
}

function restartLocal() {
  for (let i = 0; i < CONFIG.local.restart_attempts; i++) {
    try {
      shell(`systemctl --user restart ${CONFIG.local.gateway_service}`, { silent: true });
      shell(`sleep ${CONFIG.local.restart_cooldown_sec}`);
      if (isGatewayActive()) return true;
    } catch {}
  }
  return false;
}

function stopLocal() {
  try {
    shell(`systemctl --user stop ${CONFIG.local.gateway_service}`, { silent: true, ignoreError: true });
  } catch {}
}

function startRemote() {
  const cmd = `ssh -p ${CONFIG.remote.ssh_port} ${CONFIG.remote.host} "systemctl --user restart ${CONFIG.remote.gateway_service}"`;
  shell(cmd, { silent: true });
}

function stopRemote() {
  const cmd = `ssh -p ${CONFIG.remote.ssh_port} ${CONFIG.remote.host} "systemctl --user stop ${CONFIG.remote.gateway_service}"`;
  shell(cmd, { silent: true, ignoreError: true });
}

function check() {
  const state = loadState();
  const now = Date.now();

  if (state.mode === 'MASTER') {
    const healthy = isGatewayActive();
    console.log(`[${new Date().toISOString()}] Check: gateway active=${healthy}, failCount=${state.failCount}`);
    if (healthy) {
      if (state.failCount > 0) {
        state.failCount = 0;
        saveState(state);
        console.log(`[${new Date().toISOString()}] Local gateway healthy. Fail count reset.`);
      }
      return;
    }

    state.failCount++;
    state.lastCheck = now;
    saveState(state);

    notify('Gateway Health', `Local gateway down (attempt ${state.failCount}/${CONFIG.local.consecutive_failures})`);

    if (state.failCount < CONFIG.local.consecutive_failures) {
      if (restartLocal()) {
        state.failCount = 0;
        saveState(state);
        notify('Gateway Health', 'Local gateway recovered after restart');
        return;
      }
    }

    console.log(`[${new Date().toISOString()}] FAILOVER triggered after ${state.failCount} consecutive failures`);
    notify('Gateway FAILOVER', 'Local gateway failed. Switching to remote in 7 minutes...');

    stopLocal();

    setTimeout(() => {
      try {
        startRemote();
        state.mode = 'STANDBY';
        state.lastFailover = Date.now();
        state.failCount = 0;
        saveState(state);
        notify('Gateway FAILOVER', 'Remote gateway is now active. You are on STANDBY mode.');
        console.log(`[${new Date().toISOString()}] Remote gateway started.`);
      } catch (e) {
        console.error(`[${new Date().toISOString()}] Failover failed:`, e.message);
        notify('Gateway ERROR', `Failover failed: ${e.message}`);
      }
    }, CONFIG.remote.ilink_timeout_sec * 1000);

  } else if (state.mode === 'STANDBY') {
    if (isGatewayActive()) {
      console.log(`[${new Date().toISOString()}] WARN: Local gateway running while in STANDBY mode`);
      notify('Gateway WARN', 'Local gateway detected during STANDBY. Stop it to avoid conflict.');
    }
  }
}

if (require.main === module) {
  if (process.argv.includes('--daemon')) {
    console.log(`[${new Date().toISOString()}] HA monitor started in MASTER mode`);
    setInterval(check, CONFIG.local.check_interval_sec * 1000);
    check();
  } else {
    check();
  }
}

module.exports = { check, isGatewayActive, restartLocal, startRemote, stopRemote, stopLocal, loadState, saveState };
