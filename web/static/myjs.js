/**
 * AlarmPI Modern Frontend Orchestrator
 * Dynamic schema rendering, interactive zone selector, modernized timeline, and real-time Socket.IO synchronization.
 */

let socket = io();
let activeSettingsData = null;
let activeSensorTypes = [];
let activeTimelineInstance = null;
let currentModalSelectedZones = [];
let sirenAudioCtx = null;
let sirenOsc = null;
let sirenGain = null;
let sirenIsTesting = false;
let sirenTestTimeout = null;

let allProperties = {
  sensors: {},
  alarmState: 'disarmed',
  alarmArmed: false,
  currentUser: '',
  allUsers: [],
  siren: { pin: 14, enable: false }
};

$(document).ready(function() {
  initApp();
  setupEventListeners();
  setupSocketIO();
});

function initApp() {
  preloadSettings();
  refreshSensors();
  refreshLogs();
  loadSensorTypes();
}

function preloadSettings() {
  $.getJSON('/getAllSettings.json').done(function(data) {
    activeSettingsData = data;
    if (data && data.values && data.values.serene && data.values.serene.pin) {
      allProperties.siren = {
        pin: parseInt(data.values.serene.pin),
        enable: Boolean(data.values.serene.enable)
      };
    }
  });
}

function setupEventListeners() {
  $('#logtype, #loglimit').on('change', function() {
    refreshLogs();
  });

  // Enter key support for custom zone tags
  $('#sensorZoneNewInput').on('keydown', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      addCustomZoneTag();
    }
  });

  // Modal backdrop click to close
  $('.modal-backdrop').on('click', function(e) {
    if (e.target === this) {
      closeAllModals();
    }
  });

  // ESC key to close any open modal
  $(document).on('keydown', function(e) {
    if (e.key === 'Escape' || e.keyCode === 27) {
      closeAllModals();
    }
  });
}

function setupSocketIO() {
  socket.emit('join', {});

  socket.on('sensorsChanged', function(msg) {
    if (msg && msg.sensors) {
      updateSensorsUI(msg);
    } else {
      refreshSensors();
    }
  });

  socket.on('settingsChanged', function(msg) {
    if (msg && msg.sensors) {
      updateSensorsUI(msg);
    } else {
      refreshSensors();
    }
  });

  socket.on('sensorsLog', function(msg) {
    renderActivityLog(msg);
  });

  socket.on('doorChime', function(msg) {
    playDoorChimeSound();
    const sName = msg?.name || msg?.sensor_id || 'Sensor';
    showToast(`🔔 Chime: ${sName} opened`);
  });

  socket.on('entryDelay', function(msg) {
    const seconds = msg?.seconds || 30;
    const sName = msg?.name || msg?.sensor_id || 'Entry door';
    showToast(`⏳ Entry Delay: ${seconds}s grace period (${sName})`);
    playWarningBeep();
  });
}

/* ==========================================================================
   Sensors & Dashboard Rendering
   ========================================================================== */

function refreshSensors() {
  $.getJSON('/getSensors.json').done(function(data) {
    updateSensorsUI(data);
  });
}

function updateSensorsUI(data) {
  allProperties.sensors = data.sensors || {};
  allProperties.alarmState = data.alarmState || 'disarmed';
  allProperties.alarmArmed = data.alarmArmed || false;
  if (data.siren) {
    allProperties.siren = data.siren;
  }

  renderAlarmHero(data.alarmState);
  renderDynamicZoneButtons();
  renderSensorsGrid(data.sensors);
}

function renderAlarmHero(state) {
  const $ring = $('#alarmRing');
  const $icon = $('#alarmIcon');
  const $label = $('#alarmLabel');
  const $subtitle = $('#alarmSubtitle');
  const $actionBtn = $('#alarmActionBtn');

  $ring.removeClass('armed pending triggered');

  if (state === 'armed') {
    $ring.addClass('armed');
    $icon.text('🛡️');
    $label.text('Armed');
    $label.css('color', 'var(--color-armed)');
    $subtitle.text('Perimeter and interior sensors active');
    $actionBtn.removeClass('btn-arm').addClass('btn-disarm').html('<span>🔓</span> Disarm Alarm');
    if (!sirenIsTesting) stopBrowserSirenSound();
  } else if (state === 'pending') {
    $ring.addClass('pending');
    $icon.text('⏳');
    $label.text('Pending');
    $label.css('color', 'var(--color-pending)');
    $subtitle.text('Arming in progress - exit premises');
    $actionBtn.removeClass('btn-arm').addClass('btn-disarm').html('<span>❌</span> Cancel Arming');
    if (!sirenIsTesting) stopBrowserSirenSound();
  } else if (state === 'triggered') {
    $ring.addClass('triggered');
    $icon.text('🚨');
    $label.text('TRIGGERED!');
    $label.css('color', '#ef4444');
    $subtitle.text('Intruder breach detected!');
    $actionBtn.removeClass('btn-arm').addClass('btn-disarm').html('<span>🚨</span> SILENCE & DISARM');
    startBrowserSirenSound();
  } else {
    $icon.text('🔓');
    $label.text('Disarmed');
    $label.css('color', 'var(--color-disarmed)');
    $subtitle.text('System is disarmed. Standby mode.');
    $actionBtn.removeClass('btn-disarm').addClass('btn-arm').html('<span>🛡️</span> Arm Alarm');
    if (!sirenIsTesting) stopBrowserSirenSound();
  }
}

/**
 * Dynamically renders zone arming buttons ONLY for zones configured on existing sensors
 */
function renderDynamicZoneButtons() {
  const $container = $('#heroZoneButtonsContainer');
  $container.empty();

  const configuredZones = getAllSystemZones();

  if (configuredZones.length === 0) {
    return; // No custom zone tags configured
  }

  configuredZones.forEach(zone => {
    const formattedName = zone.charAt(0).toUpperCase() + zone.slice(1);
    const zoneBtn = $(`
      <button class="btn-zone" onclick="armAlarm('${zone}')" title="Arm ${formattedName} Zone">
        ${formattedName}
      </button>
    `);
    $container.append(zoneBtn);
  });
}

/**
 * Returns all unique zone names currently present across all sensors
 */
function getAllSystemZones() {
  const zonesSet = new Set();
  $.each(allProperties.sensors, function(id, s) {
    if (s.zones) {
      if (Array.isArray(s.zones)) {
        s.zones.forEach(z => { if (z && z.trim()) zonesSet.add(z.trim().toLowerCase()); });
      } else if (typeof s.zones === 'string') {
        s.zones.split(',').forEach(z => { if (z && z.trim()) zonesSet.add(z.trim().toLowerCase()); });
      }
    }
  });
  return Array.from(zonesSet).sort();
}

const SENSOR_DEVICE_CLASSES = {
  door: { icon: '🚪', label: 'Door' },
  window: { icon: '🪟', label: 'Window' },
  motion: { icon: '🏃', label: 'Motion' },
  tamper: { icon: '⚠️', label: 'Tamper' },
  smoke: { icon: '💨', label: 'Smoke' },
  glass: { icon: '🔨', label: 'Glass Break' },
  vibration: { icon: '📳', label: 'Vibration' },
  generic: { icon: '🔌', label: 'Generic' }
};

function getSensorDeviceMeta(sensor) {
  if (sensor && sensor.device_class && SENSOR_DEVICE_CLASSES[sensor.device_class]) {
    return { key: sensor.device_class, ...SENSOR_DEVICE_CLASSES[sensor.device_class] };
  }
  const name = ((sensor && sensor.name) || '').toLowerCase();
  if (name.includes('motion') || name.includes('pir') || name.includes('move')) return { key: 'motion', ...SENSOR_DEVICE_CLASSES.motion };
  if (name.includes('window')) return { key: 'window', ...SENSOR_DEVICE_CLASSES.window };
  if (name.includes('smoke') || name.includes('fire')) return { key: 'smoke', ...SENSOR_DEVICE_CLASSES.smoke };
  if (name.includes('tamper')) return { key: 'tamper', ...SENSOR_DEVICE_CLASSES.tamper };
  if (name.includes('glass')) return { key: 'glass', ...SENSOR_DEVICE_CLASSES.glass };
  if (name.includes('vibrat')) return { key: 'vibration', ...SENSOR_DEVICE_CLASSES.vibration };
  return { key: 'door', ...SENSOR_DEVICE_CLASSES.door };
}

function renderSensorsGrid(sensors) {
  const $grid = $('#sensorsGrid');
  $grid.empty();

  const sensorKeys = Object.keys(sensors || {});
  if (sensorKeys.length === 0) {
    $grid.html(`
      <div style="grid-column: 1 / -1; text-align: center; padding: 48px 24px; color: var(--text-muted);">
        <div style="font-size: 3rem; margin-bottom: 12px; opacity: 0.5;">🔌</div>
        <p style="font-size: 1.2rem; margin-bottom: 8px;">No sensors configured yet</p>
        <p style="font-size: 0.9rem;">Click the <b>+</b> button on the bottom right to add your first sensor.</p>
      </div>
    `);
    return;
  }

  $.each(sensors, function(id, s) {
    const isEnabled = s.enabled !== false;
    const isOnline = s.online !== false;
    const isAlert = s.alert === true;

    let statusText = 'Normal';
    let statusClass = '';
    let cardBorderGlow = '';

    if (!isOnline) {
      statusText = 'Offline / Error';
      statusClass = 'offline';
      cardBorderGlow = 'border-color: rgba(59, 130, 246, 0.5);';
    } else if (isAlert && isEnabled) {
      statusText = 'Breach / Alert';
      statusClass = 'alert';
      cardBorderGlow = 'border-color: rgba(239, 68, 68, 0.7); box-shadow: 0 0 15px rgba(239, 68, 68, 0.3);';
    } else if (!isEnabled) {
      statusText = 'Bypassed';
      statusClass = 'disabled';
    }

    const devMeta = getSensorDeviceMeta(s);

    let zonesHtml = '';
    if (s.zones && Array.isArray(s.zones)) {
      zonesHtml = s.zones.map(z => `<span class="zone-chip">${z}</span>`).join('');
    } else if (typeof s.zones === 'string' && s.zones) {
      zonesHtml = `<span class="zone-chip">${s.zones}</span>`;
    }

    if (s.behavior === '24hours') {
      zonesHtml += `<span class="zone-chip" style="color: #fca5a5; background: rgba(239, 68, 68, 0.15);">24-Hours</span>`;
    } else if (s.behavior === 'entry_exit') {
      zonesHtml += `<span class="zone-chip" style="color: #93c5fd; background: rgba(59, 130, 246, 0.15);">Entry/Exit</span>`;
    } else if (s.behavior === 'instant') {
      zonesHtml += `<span class="zone-chip" style="color: #fdba74; background: rgba(249, 115, 22, 0.15);">Instant</span>`;
    } else if (s.behavior === 'chime') {
      zonesHtml += `<span class="zone-chip" style="color: #a7f3d0; background: rgba(16, 185, 129, 0.15);">Chime</span>`;
    }

    const cardHtml = `
      <div class="sensor-card" style="${cardBorderGlow}">
        <div class="sensor-card-top">
          <span class="sensor-type-badge">${devMeta.icon} ${devMeta.label} <span style="opacity: 0.65; font-size: 0.7rem; margin-left: 3px;">(${s.type || 'GPIO'})</span></span>
          <div>
            <label class="switch">
              <input type="checkbox" ${isEnabled ? 'checked' : ''} onchange="toggleSensorEnabled('${id}', this.checked)">
              <span class="slider slider-green"></span>
            </label>
          </div>
        </div>
        <div>
          <h3 class="sensor-card-name">${s.name || id}</h3>
          <div class="sensor-zones-container">${zonesHtml}</div>
        </div>
        <div class="sensor-card-bottom">
          <span class="status-pill">
            <span class="status-indicator-dot ${statusClass}"></span>
            ${statusText}
          </span>
          <button class="sensor-config-btn" onclick="openEditSensorModal('${id}')" title="Configure Sensor">
            <span>⚙️</span> Configure
          </button>
        </div>
      </div>
    `;

    $grid.append(cardHtml);
  });
}

function toggleSensorEnabled(sensorId, isChecked) {
  if (allProperties.sensors[sensorId]) {
    allProperties.sensors[sensorId].enabled = isChecked;
  }
  socket.emit('setSensorState', { sensor: sensorId, enabled: isChecked });
  showToast(isChecked ? 'Sensor armed' : 'Sensor bypassed');
}

/* ==========================================================================
   Arm / Disarm & Siren Controls
   ========================================================================== */

function handleMainAlarmAction() {
  if (allProperties.alarmState === 'disarmed') {
    armAlarm('away');
  } else {
    disarmAlarm();
  }
}

function armAlarm(zone) {
  if (zone && zone !== 'away') {
    $.getJSON(`/activateAlarmZone?zones=${encodeURIComponent(zone)}`).done(function() {
      showToast(`Alarm armed for zone: ${zone}`);
    });
  } else {
    socket.emit('activateAlarm');
    showToast('Alarm armed');
  }
}

function disarmAlarm() {
  socket.emit('deactivateAlarm');
  showToast('Alarm disarmed');
}

function startBrowserSirenSound() {
  // 1. Try HTML5 audio element
  const audioEl = document.getElementById('audioalert');
  if (audioEl) {
    audioEl.currentTime = 0;
    audioEl.play().catch(e => console.log('HTML5 audio play blocked/deferred:', e));
  }

  // 2. Synthesize dual-tone alarm siren using Web Audio API for 100% browser compatibility
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    if (!sirenAudioCtx) {
      sirenAudioCtx = new AudioContextClass();
    }
    if (sirenAudioCtx.state === 'suspended') {
      sirenAudioCtx.resume();
    }

    stopWebAudioSiren();

    const osc = sirenAudioCtx.createOscillator();
    const gain = sirenAudioCtx.createGain();

    osc.type = 'sawtooth';
    const now = sirenAudioCtx.currentTime;
    
    // Siren frequency sweeps
    for (let i = 0; i < 25; i++) {
      const t = now + i * 0.4;
      osc.frequency.setValueAtTime(650, t);
      osc.frequency.linearRampToValueAtTime(1150, t + 0.2);
      osc.frequency.linearRampToValueAtTime(650, t + 0.4);
    }

    gain.gain.setValueAtTime(0.2, now);
    osc.connect(gain);
    gain.connect(sirenAudioCtx.destination);
    osc.start(now);
    sirenOsc = osc;
    sirenGain = gain;
  } catch (err) {
    console.warn('Web Audio synthesis error:', err);
  }
}

function stopBrowserSirenSound() {
  const audioEl = document.getElementById('audioalert');
  if (audioEl) {
    audioEl.pause();
    audioEl.currentTime = 0;
  }
  stopWebAudioSiren();
}

function stopWebAudioSiren() {
  if (sirenOsc) {
    try {
      sirenOsc.stop();
      sirenOsc.disconnect();
    } catch (e) {}
    sirenOsc = null;
  }
}

function playDoorChimeSound() {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    if (!sirenAudioCtx) {
      sirenAudioCtx = new AudioContextClass();
    }
    if (sirenAudioCtx.state === 'suspended') {
      sirenAudioCtx.resume();
    }

    const now = sirenAudioCtx.currentTime;

    // High chime tone (880Hz - A5)
    const osc1 = sirenAudioCtx.createOscillator();
    const gain1 = sirenAudioCtx.createGain();
    osc1.type = 'sine';
    osc1.frequency.setValueAtTime(880, now);
    gain1.gain.setValueAtTime(0.25, now);
    gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
    osc1.connect(gain1);
    gain1.connect(sirenAudioCtx.destination);
    osc1.start(now);
    osc1.stop(now + 0.4);

    // Warm resonant tone (587.33Hz - D5)
    const osc2 = sirenAudioCtx.createOscillator();
    const gain2 = sirenAudioCtx.createGain();
    osc2.type = 'sine';
    osc2.frequency.setValueAtTime(587.33, now + 0.12);
    gain2.gain.setValueAtTime(0.3, now + 0.12);
    gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.65);
    osc2.connect(gain2);
    gain2.connect(sirenAudioCtx.destination);
    osc2.start(now + 0.12);
    osc2.stop(now + 0.7);
  } catch (err) {
    console.warn('Door chime audio synthesis error:', err);
  }
}

function playWarningBeep() {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    if (!sirenAudioCtx) {
      sirenAudioCtx = new AudioContextClass();
    }
    if (sirenAudioCtx.state === 'suspended') {
      sirenAudioCtx.resume();
    }

    const now = sirenAudioCtx.currentTime;
    for (let i = 0; i < 4; i++) {
      const osc = sirenAudioCtx.createOscillator();
      const gain = sirenAudioCtx.createGain();
      const t = now + i * 0.3;
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(1046.5, t); // C6 warning pulse
      gain.gain.setValueAtTime(0.2, t);
      gain.gain.exponentialRampToValueAtTime(0.001, t + 0.15);
      osc.connect(gain);
      gain.connect(sirenAudioCtx.destination);
      osc.start(t);
      osc.stop(t + 0.18);
    }
  } catch (err) {
    console.warn('Warning beep audio synthesis error:', err);
  }
}

function toggleSirenTest() {
  const $btn = $('.btn-siren-test');

  if (sirenIsTesting) {
    // Cancel running test
    if (sirenTestTimeout) clearTimeout(sirenTestTimeout);
    sirenIsTesting = false;
    stopBrowserSirenSound();
    $.getJSON('/stopSiren');
    $btn.removeClass('sounding').html('🔊 Sound Siren Test');
    showToast('Siren test stopped');
    return;
  }

  sirenIsTesting = true;
  $btn.addClass('sounding').html('🔊 Silencing in 3s...');
  startBrowserSirenSound();
  $.getJSON('/startSiren');
  showToast('Siren test sounding (Browser & Hardware)...');

  sirenTestTimeout = setTimeout(() => {
    sirenIsTesting = false;
    stopBrowserSirenSound();
    $.getJSON('/stopSiren');
    $btn.removeClass('sounding').html('🔊 Sound Siren Test');
    showToast('Siren test complete');
  }, 3000);
}

/* ==========================================================================
   Activity Event Logs
   ========================================================================== */

function refreshLogs() {
  const limit = $('#loglimit').val() || 30;
  const type = $('#logtype').val() || 'all';

  $.getJSON(`/getSensorsLog.json?saveLimit=True&limit=${limit}&type=${type}`).done(function(data) {
    renderActivityLog(data);
  });
}

function renderActivityLog(data) {
  const $list = $('#activityList');
  $list.empty();

  if (!data || !data.log || data.log.length === 0) {
    $list.append('<li class="activity-item" style="color: var(--text-muted); text-align: center;">No log events found</li>');
    return;
  }

  const logs = [...data.log];
  logs.forEach(function(item) {
    let itemText = typeof item === 'string' ? item : JSON.stringify(item);
    let itemClass = '';

    if (itemText.includes('Alert Sensor') || itemText.includes('Intruder')) itemClass = 'sensor-on';
    else if (itemText.includes('Stop Alert')) itemClass = 'sensor-off';
    else if (itemText.includes('Alarm activated') || itemText.includes('Alarm deactivated')) itemClass = 'alarm';
    else if (itemText.includes('user_action') || itemText.includes('sensor:')) itemClass = 'user';

    $list.prepend(`<li class="activity-item ${itemClass}">${itemText}</li>`);
  });
}

/* ==========================================================================
   Dynamic Settings Schema Rendering (Wrapped Flex Tabs - No Horizontal Scrollbar)
   ========================================================================== */

function openSettingsModal() {
  $.getJSON('/getAllSettings.json').done(function(data) {
    activeSettingsData = data;
    renderDynamicSettings(data);
    $('#settingsModalBackdrop').css('display', 'flex');
  });
}

function renderDynamicSettings(data) {
  const $tabsNav = $('#settingsTabsNav');
  const $container = $('#settingsTabContent');
  $tabsNav.empty();
  $container.empty();

  const sections = data.sections || [];
  const values = data.values || {};
  const statuses = data.statuses || {};

  // 1. Render primary combined System Tab Button
  const systemTabBtn = $(`
    <button id="settings_tab_btn_system" class="settings-tab-btn active" onclick="switchSettingsTab('system')">
      <span class="tab-status-dot online"></span>
      System
    </button>
  `);
  $tabsNav.append(systemTabBtn);

  // 2. Render all modular Notifier plugin tab buttons
  sections.forEach((section) => {
    if (section.id === 'system' || section.id === 'settings' || section.id === 'ui') return;
    const sectionStatus = statuses[section.id];
    let statusDotClass = '';
    if (sectionStatus === true) statusDotClass = 'online';
    else if (sectionStatus === false) statusDotClass = 'offline';

    const tabBtn = $(`
      <button id="settings_tab_btn_${section.id}" class="settings-tab-btn" onclick="switchSettingsTab('${section.id}')">
        <span class="tab-status-dot ${statusDotClass}"></span>
        ${section.title}
      </button>
    `);
    $tabsNav.append(tabBtn);
  });

  // 3. Render Combined System Pane (General + Account & UI + Session/Power)
  const uiVals = values.ui || {};
  const settingsVals = values.settings || {};

  const systemPaneHtml = `
    <div class="settings-pane" id="pane_system">
      <div class="settings-pane-header">
        <div class="settings-pane-title-group">
          <h3 class="settings-pane-title">System & Account Settings</h3>
          <p class="settings-pane-desc">Configure system parameters, operator account credentials, web interface security, and daemon actions.</p>
        </div>
      </div>

      <!-- Group 1: General Parameters -->
      <div class="settings-subgroup">
        <h4 class="settings-subgroup-title"><span>⚙️</span> General Parameters</h4>
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">System Timezone</label>
            <input type="text" class="form-control" id="field_settings_timezone" value="${settingsVals.timezone || 'Europe/Athens'}" placeholder="e.g. Europe/Athens, America/New_York">
            <span class="form-help">Timezone for logging and sensor alert timestamps</span>
          </div>
          <div class="form-group">
            <label class="form-label">Log Retention (Max Lines)</label>
            <input type="number" class="form-control" id="field_settings_trim" value="${settingsVals.trim !== undefined ? settingsVals.trim : 1000}">
            <span class="form-help">Maximum activity events preserved in memory</span>
          </div>
        </div>
      </div>

      <!-- Group 2: Smart Arming & Delays -->
      <div class="settings-subgroup">
        <h4 class="settings-subgroup-title"><span>🛡️</span> Smart Arming & Delays</h4>
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">Exit Delay (Seconds)</label>
            <input type="number" class="form-control" id="field_settings_exit_delay" value="${settingsVals.exit_delay !== undefined ? settingsVals.exit_delay : 0}">
            <span class="form-help">Countdown before alarm arms (0 = instant arming)</span>
          </div>
          <div class="form-group">
            <label class="form-label">Entry Delay (Seconds)</label>
            <input type="number" class="form-control" id="field_settings_entry_delay" value="${settingsVals.entry_delay !== undefined ? settingsVals.entry_delay : 30}">
            <span class="form-help">Grace period to disarm after opening entry door</span>
          </div>
          <div class="form-group">
            <label class="form-label">Arm After Closing Door</label>
            <label class="switch">
              <input type="checkbox" id="field_settings_arm_after_closing" ${settingsVals.arm_after_closing !== false ? 'checked' : ''}>
              <span class="slider"></span>
            </label>
            <span class="form-help">Immediately arm when exit door is closed without waiting for delay</span>
          </div>
          <div class="form-group">
            <label class="form-label">Auto-Bypass Open Sensors</label>
            <label class="switch">
              <input type="checkbox" id="field_settings_auto_bypass_open" ${settingsVals.auto_bypass_open ? 'checked' : ''}>
              <span class="slider"></span>
            </label>
            <span class="form-help">Automatically bypass opened sensors on arming instead of waiting</span>
          </div>
          <div class="form-group">
            <label class="form-label">Door Chime (Disarmed Mode)</label>
            <label class="switch">
              <input type="checkbox" id="field_settings_door_chime" ${settingsVals.door_chime ? 'checked' : ''}>
              <span class="slider"></span>
            </label>
            <span class="form-help">Play gentle chime when doors/windows open while disarmed</span>
          </div>
          <div class="form-group">
            <label class="form-label">Siren Cutoff Duration (Seconds)</label>
            <input type="number" class="form-control" id="field_settings_siren_duration" value="${settingsVals.siren_duration !== undefined ? settingsVals.siren_duration : 180}">
            <span class="form-help">Automatically silence siren after duration (0 = continuous)</span>
          </div>
        </div>
      </div>

      <!-- Group 3: Account & Web Security -->
      <div class="settings-subgroup">
        <h4 class="settings-subgroup-title"><span>🔐</span> Account & Web Security</h4>
        <div class="form-grid">
          <div class="form-group">
            <label class="form-label">Active User</label>
            <input type="text" class="form-control" id="field_ui_username" value="${uiVals.username || ''}" readonly>
            <span class="form-help">Operator account identifier</span>
          </div>
          <div class="form-group">
            <label class="form-label">Change Password</label>
            <input type="password" class="form-control" id="field_ui_password" value="${uiVals.password || ''}" placeholder="Enter new password">
            <span class="form-help">Web interface login credentials</span>
          </div>
          <div class="form-group">
            <label class="form-label">Web Server Port</label>
            <input type="number" class="form-control" id="field_ui_port" value="${uiVals.port || 5000}">
            <span class="form-help">Port for HTTP/HTTPS dashboard access</span>
          </div>
          <div class="form-group">
            <label class="form-label">Enable HTTPS (SSL)</label>
            <label class="switch">
              <input type="checkbox" id="field_ui_https" ${uiVals.https ? 'checked' : ''}>
              <span class="slider"></span>
            </label>
            <span class="form-help">Requires SSL certificates in config/</span>
          </div>
        </div>
      </div>

      <!-- Group 4: Session & Daemon Actions -->
      <div class="settings-subgroup">
        <h4 class="settings-subgroup-title"><span>⚡</span> Session & Daemon Actions</h4>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px;">
          <div style="background: rgba(15, 23, 42, 0.6); padding: 14px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
            <h5 style="font-size: 0.9rem; font-weight: 600; margin-bottom: 4px; color: #f8fafc;">Switch Active User</h5>
            <p style="font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 10px;">Switch dashboard to another configured operator.</p>
            <div style="display: flex; gap: 8px;">
              <select id="settingsUserSelect" class="form-control" style="flex: 1; padding: 6px 10px;"></select>
              <button class="btn-secondary" style="padding: 6px 14px; font-size: 0.85rem;" onclick="changeUser()">Switch</button>
            </div>
          </div>
          <div style="background: rgba(15, 23, 42, 0.6); padding: 14px; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
            <h5 style="font-size: 0.9rem; font-weight: 600; margin-bottom: 4px; color: #f8fafc;">Service Controls</h5>
            <p style="font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 10px;">Restart daemon service or end current session.</p>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
              <button class="btn-secondary" style="padding: 6px 12px; font-size: 0.85rem;" onclick="restartService()">🔄 Restart Service</button>
              <button class="btn-danger" style="padding: 6px 12px; font-size: 0.85rem;" onclick="logout()">🚪 Logout</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;
  $container.append(systemPaneHtml);

  // 4. Render modular Notifier plugin panes
  sections.forEach((section) => {
    if (section.id === 'system' || section.id === 'settings' || section.id === 'ui') return;
    const sectionVals = values[section.id] || {};
    const isMasterEnabled = sectionVals.enable !== undefined ? sectionVals.enable : true;

    let fieldsHtml = '';
    (section.fields || []).forEach(f => {
      const fieldVal = sectionVals[f.name] !== undefined ? sectionVals[f.name] : (f.default !== undefined ? f.default : '');
      fieldsHtml += renderFormField(section.id, f, fieldVal);
    });

    const paneHtml = `
      <div class="settings-pane" id="pane_${section.id}" style="display: none;">
        <div class="settings-pane-header">
          <div class="settings-pane-title-group">
            <h3 class="settings-pane-title">${section.title}</h3>
            <p class="settings-pane-desc">${section.description || 'Configure parameters and integration options for this component.'}</p>
          </div>
          ${section.has_enable ? `
            <div class="settings-pane-toggle">
              <span class="settings-toggle-label" style="font-size: 0.85rem; font-weight: 600; color: var(--text-secondary);">Enable</span>
              <label class="switch">
                <input type="checkbox" id="field_${section.id}_enable" ${isMasterEnabled ? 'checked' : ''}>
                <span class="slider slider-green"></span>
              </label>
            </div>
          ` : ''}
        </div>
        <div class="form-grid">
          ${fieldsHtml}
        </div>
      </div>
    `;

    $container.append(paneHtml);
  });

  // Attach live enable-toggle listener to update tab status dots immediately
  $('.settings-pane input[id$="_enable"]').off('change').on('change', function() {
    const secId = this.id.replace('field_', '').replace('_enable', '');
    const isEnabled = $(this).prop('checked');
    const $dot = $(`#settings_tab_btn_${secId} .tab-status-dot`);
    if (isEnabled) {
      $dot.removeClass('offline').addClass('online');
    } else {
      $dot.removeClass('online').addClass('offline');
    }
    if (secId === 'serene') {
      if (!allProperties.siren) allProperties.siren = { pin: 14 };
      allProperties.siren.enable = isEnabled;
    }
  });

  populatePinSelectors();
  loadUsersManagement();
}

/**
 * Returns map of all used BCM GPIO pins across sensors and siren relay
 */
function getSystemUsedPins(excludeSensorId = null) {
  const pinMap = {};

  // Check sensors
  $.each(allProperties.sensors, function(id, s) {
    if (excludeSensorId && id === excludeSensorId) return;
    if (s.pin !== undefined && s.pin !== null && s.pin !== '') {
      const pinNum = parseInt(s.pin);
      if (!isNaN(pinNum)) {
        pinMap[pinNum] = `In use by "${s.name || id}"`;
      }
    }
  });

  // Check Siren pin ONLY if Siren is ENABLED and we are not configuring the siren itself
  if (excludeSensorId !== 'serene' && excludeSensorId !== 'siren') {
    const sirenEnabled = (allProperties.siren?.enable !== undefined)
      ? Boolean(allProperties.siren.enable)
      : Boolean(activeSettingsData?.values?.serene?.enable);

    if (sirenEnabled) {
      let sirenPin = allProperties.siren?.pin;
      if (sirenPin === undefined || sirenPin === null) {
        sirenPin = activeSettingsData?.values?.serene?.pin || activeSettingsData?.values?.settings?.serene?.pin || 14;
      }
      const pinNum = parseInt(sirenPin);
      if (!isNaN(pinNum) && pinNum > 0 && !pinMap[pinNum]) {
        pinMap[pinNum] = 'In use by Siren Relay';
      }
    }
  }

  return pinMap;
}

/**
 * Populates a select element with BCM Pin 1-27 with clear usage indications, disabling in-use pins
 */
function renderPinSelectOptions($select, currentVal, excludeSensorId = null) {
  const isEditing = Boolean(excludeSensorId && allProperties.sensors && allProperties.sensors[excludeSensorId]);
  const isSirenConfig = (excludeSensorId === 'serene' || excludeSensorId === 'siren');
  const currentPin = parseInt(currentVal) || 0;
  const usedPinsMap = getSystemUsedPins(excludeSensorId);
  $select.empty();

  // If adding a new sensor and default pin is already taken (or 0), pick the first genuinely free pin
  let selectedPin = currentPin;
  if (!isEditing && !isSirenConfig && (selectedPin === 0 || usedPinsMap[selectedPin])) {
    for (let i = 1; i <= 27; i++) {
      if (!usedPinsMap[i]) {
        selectedPin = i;
        break;
      }
    }
  }

  for (let i = 1; i <= 27; i++) {
    const isSelected = (i === selectedPin);
    const usageText = usedPinsMap[i];
    const isDisabled = Boolean(usageText);
    let label = `BCM Pin ${i}`;

    if (usageText) {
      label += ` — (${usageText})`;
    } else if ((isEditing || isSirenConfig) && isSelected) {
      label += ` — (Current)`;
    }

    $select.append(`<option value="${i}" ${isSelected ? 'selected' : ''} ${isDisabled ? 'disabled' : ''}>${label}</option>`);
  }
}

function renderFormField(sectionId, field, value) {
  const fieldId = `field_${sectionId}_${field.name}`;
  const label = field.label || field.name;
  const help = field.help ? `<span class="form-help">${field.help}</span>` : '';
  const isReadOnly = field.readonly ? 'readonly' : '';

  if (field.type === 'boolean' && field.name !== 'enable') {
    const isChecked = value === true || value === 'true';
    return `
      <div class="form-group">
        <label class="form-label">${label}</label>
        <label class="switch">
          <input type="checkbox" id="${fieldId}" ${isChecked ? 'checked' : ''}>
          <span class="slider"></span>
        </label>
        ${help}
      </div>
    `;
  }

  if (field.type === 'pin') {
    return `
      <div class="form-group">
        <label class="form-label">${label}</label>
        <select class="form-control bcm-pin-select" id="${fieldId}" data-current="${value}"></select>
        ${help}
      </div>
    `;
  }

  if (field.type === 'password') {
    return `
      <div class="form-group">
        <label class="form-label">${label}</label>
        <input type="password" class="form-control" id="${fieldId}" value="${value || ''}" placeholder="${field.placeholder || ''}" ${isReadOnly}>
        ${help}
      </div>
    `;
  }

  if (field.type === 'number') {
    return `
      <div class="form-group">
        <label class="form-label">${label}</label>
        <input type="number" class="form-control" id="${fieldId}" value="${value !== undefined ? value : ''}" placeholder="${field.placeholder || ''}" ${isReadOnly}>
        ${help}
      </div>
    `;
  }

  if (field.type === 'list') {
    const listVal = Array.isArray(value) ? value.join(', ') : (value || '');
    return `
      <div class="form-group full-width">
        <label class="form-label">${label} (Comma-separated)</label>
        <input type="text" class="form-control" id="${fieldId}" value="${listVal}" placeholder="${field.placeholder || ''}">
        ${help}
      </div>
    `;
  }

  return `
    <div class="form-group">
      <label class="form-label">${label}</label>
      <input type="text" class="form-control" id="${fieldId}" value="${value || ''}" placeholder="${field.placeholder || ''}" ${isReadOnly}>
      ${help}
    </div>
  `;
}

function switchSettingsTab(sectionId) {
  $('.settings-tab-btn').removeClass('active');
  $(`#settings_tab_btn_${sectionId}`).addClass('active');
  $('.settings-pane').hide();
  $(`#pane_${sectionId}`).show();
}

function populatePinSelectors() {
  $('.bcm-pin-select').each(function() {
    const $select = $(this);
    const currentPin = parseInt($select.data('current') || 14);
    renderPinSelectOptions($select, currentPin, 'serene');
  });
}

function loadUsersManagement() {
  $.getJSON('/getUsers').done(function(data) {
    const $select = $('#settingsUserSelect');
    $select.empty();
    (data.allusers || []).forEach(u => {
      $select.append(`<option value="${u}" ${u === data.current ? 'selected' : ''}>${u}</option>`);
    });
  });
}

function saveDynamicSettings() {
  if (!activeSettingsData) return;

  const payload = {
    settings: {
      timezone: $('#field_settings_timezone').val() || 'Europe/Athens',
      trim: parseInt($('#field_settings_trim').val()) || 1000,
      exit_delay: parseInt($('#field_settings_exit_delay').val()) || 0,
      entry_delay: parseInt($('#field_settings_entry_delay').val()) || 0,
      arm_after_closing: $('#field_settings_arm_after_closing').prop('checked'),
      auto_bypass_open: $('#field_settings_auto_bypass_open').prop('checked'),
      door_chime: $('#field_settings_door_chime').prop('checked'),
      siren_duration: parseInt($('#field_settings_siren_duration').val()) || 180
    },
    ui: {
      password: $('#field_ui_password').val(),
      port: parseInt($('#field_ui_port').val()) || 5000,
      https: $('#field_ui_https').prop('checked')
    }
  };

  const sections = activeSettingsData.sections || [];
  sections.forEach(sec => {
    if (sec.id === 'system' || sec.id === 'settings' || sec.id === 'ui') return;
    payload[sec.id] = {};
    if (sec.has_enable) {
      payload[sec.id]['enable'] = $(`#field_${sec.id}_enable`).prop('checked');
    }

    (sec.fields || []).forEach(f => {
      const el = document.getElementById(`field_${sec.id}_${f.name}`);
      if (!el) return;

      if (f.type === 'boolean') {
        payload[sec.id][f.name] = $(el).prop('checked');
      } else if (f.type === 'number' || f.type === 'pin') {
        payload[sec.id][f.name] = parseInt($(el).val()) || 0;
      } else if (f.type === 'list') {
        const raw = $(el).val() || '';
        payload[sec.id][f.name] = raw.split(',').map(s => s.trim()).filter(s => s.length > 0);
      } else {
        payload[sec.id][f.name] = $(el).val();
      }
    });
  });

  const $saveBtn = $('#settingsModalBackdrop .btn-arm');
  const origBtnText = $saveBtn.text();
  $saveBtn.prop('disabled', true).text('Saving...');

  $.ajax({
    type: 'POST',
    url: '/api/settings',
    contentType: 'application/json',
    data: JSON.stringify(payload),
    success: function() {
      $saveBtn.prop('disabled', false).text(origBtnText);
      if (payload.serene) {
        allProperties.siren = {
          pin: parseInt(payload.serene.pin || 14),
          enable: Boolean(payload.serene.enable)
        };
      }
      showToast('Settings saved successfully!');
      closeAllModals();
      refreshSensors();
    },
    error: function() {
      $saveBtn.prop('disabled', false).text(origBtnText);
      showToast('Error saving settings');
    }
  });
}

/* ==========================================================================
   Dynamic Sensor Modal with Interactive Zone Tag Selector
   ========================================================================== */

function loadSensorTypes() {
  $.getJSON('/getSensorTypes.json').done(function(data) {
    activeSensorTypes = data || [];
  });
}

function openAddSensorModal() {
  $('#sensorModalTitle').text('Add New Sensor');
  $('#sensorModalId').val('');
  $('#sensorInputName').val('');
  $('#sensorInputDeviceClass').val('door');
  $('#sensorInputBehavior').val('normal');
  $('#sensorDeleteBtn').hide();

  currentModalSelectedZones = [];
  renderZoneTagSelector();

  renderSensorTypeDropdown();
  renderDynamicSensorFields(activeSensorTypes[0]?.type || 'GPIO');
  $('#sensorModalBackdrop').css('display', 'flex');
}

function openEditSensorModal(sensorId) {
  const sensor = allProperties.sensors[sensorId];
  if (!sensor) return;

  const devMeta = getSensorDeviceMeta(sensor);

  $('#sensorModalTitle').text('Edit Sensor');
  $('#sensorModalId').val(sensorId);
  $('#sensorInputName').val(sensor.name || '');
  $('#sensorInputDeviceClass').val(devMeta.key || 'door');
  $('#sensorInputBehavior').val(sensor.behavior || 'normal');
  $('#sensorDeleteBtn').show().off('click').on('click', () => deleteSensor(sensorId));

  if (Array.isArray(sensor.zones)) {
    currentModalSelectedZones = [...sensor.zones];
  } else if (typeof sensor.zones === 'string' && sensor.zones) {
    currentModalSelectedZones = sensor.zones.split(',').map(z => z.trim()).filter(z => z.length > 0);
  } else {
    currentModalSelectedZones = [];
  }
  renderZoneTagSelector();

  renderSensorTypeDropdown(sensor.type);
  renderDynamicSensorFields(sensor.type, sensor);

  // Load sensor-specific log history
  $.getJSON(`/getSensorsLog.json?limit=25&type=sensor&filterText=${encodeURIComponent(sensor.name || sensorId)}`).done(function(data) {
    const $logContainer = $('#sensorDetailLogs');
    $logContainer.empty();
    if (data && data.log && data.log.length > 0) {
      data.log.forEach(l => {
        $logContainer.prepend(`<div style="padding: 6px; font-size: 0.8rem; border-bottom: 1px solid var(--border-color);">${l}</div>`);
      });
    } else {
      $logContainer.html('<div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding: 10px;">No recent events for this sensor</div>');
    }
  });

  $('#sensorModalBackdrop').css('display', 'flex');
}

let zoneDropdownActiveIndex = 0;
let currentDropdownItems = [];

function focusZoneInput() {
  $('#sensorZoneNewInput').focus();
}

/**
 * GitHub-Style Interactive Zone Tag Selector Component
 */
function renderZoneTagSelector() {
  const $activeContainer = $('#sensorActiveZonesContainer');
  const $input = $('#sensorZoneNewInput');
  const $dropdown = $('#zoneAutocompleteDropdown');
  $activeContainer.empty();

  // Render active selected tags
  currentModalSelectedZones.forEach(zone => {
    const tagHtml = $(`
      <span class="github-topic-tag">
        ${zone}
        <span class="tag-remove" onclick="removeZoneTag('${zone}')">&times;</span>
      </span>
    `);
    $activeContainer.append(tagHtml);
  });

  // Setup input events
  $input.off('input focus keydown');

  $input.on('focus', function() {
    updateZoneAutocompleteDropdown($(this).val());
  });

  $input.on('input', function() {
    updateZoneAutocompleteDropdown($(this).val());
  });

  $input.on('keydown', function(e) {
    const query = $(this).val().trim().toLowerCase();

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (currentDropdownItems.length > 0) {
        zoneDropdownActiveIndex = (zoneDropdownActiveIndex + 1) % currentDropdownItems.length;
        highlightDropdownItem();
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (currentDropdownItems.length > 0) {
        zoneDropdownActiveIndex = (zoneDropdownActiveIndex - 1 + currentDropdownItems.length) % currentDropdownItems.length;
        highlightDropdownItem();
      }
    } else if (e.key === 'Enter' || e.key === 'Tab' || e.key === ',') {
      e.preventDefault();
      if (currentDropdownItems.length > 0 && zoneDropdownActiveIndex >= 0 && zoneDropdownActiveIndex < currentDropdownItems.length) {
        selectZoneTag(currentDropdownItems[zoneDropdownActiveIndex].value);
      } else if (query) {
        selectZoneTag(query);
      }
    } else if (e.key === 'Backspace') {
      if (!$(this).val() && currentModalSelectedZones.length > 0) {
        currentModalSelectedZones.pop();
        renderZoneTagSelector();
        updateZoneAutocompleteDropdown('');
      }
    } else if (e.key === 'Escape') {
      $dropdown.hide();
    }
  });

  // Close dropdown on outside click
  $(document).off('click.zoneDropdown').on('click.zoneDropdown', function(e) {
    if (!$(e.target).closest('#githubTopicContainer, #zoneAutocompleteDropdown').length) {
      $('#zoneAutocompleteDropdown').hide();
    }
  });
}

function updateZoneAutocompleteDropdown(query) {
  const q = (query || '').trim().toLowerCase();
  const $dropdown = $('#zoneAutocompleteDropdown');
  $dropdown.empty();
  currentDropdownItems = [];
  zoneDropdownActiveIndex = 0;

  const systemZones = getAllSystemZones();
  const availableExisting = systemZones.filter(z => !currentModalSelectedZones.includes(z));

  // If typing something new, offer to create it
  if (q && !currentModalSelectedZones.includes(q)) {
    const exactMatch = availableExisting.find(z => z === q);
    if (!exactMatch) {
      currentDropdownItems.push({
        value: q,
        label: `✨ Create "<b>${q}</b>"`,
        badge: 'New Tag'
      });
    }
  }

  // Matching existing zones
  availableExisting.forEach(z => {
    if (!q || z.includes(q)) {
      currentDropdownItems.push({
        value: z,
        label: q ? z.replace(new RegExp(`(${q})`, 'gi'), '<b>$1</b>') : z,
        badge: 'Existing Zone'
      });
    }
  });

  if (currentDropdownItems.length === 0) {
    $dropdown.hide();
    return;
  }

  currentDropdownItems.forEach((item, idx) => {
    const itemEl = $(`
      <div class="github-topic-dropdown-item ${idx === 0 ? 'active' : ''}" data-index="${idx}">
        <span>${item.label}</span>
        <span class="item-action">${item.badge}</span>
      </div>
    `);
    itemEl.on('mousedown', function(e) {
      e.preventDefault();
      selectZoneTag(item.value);
    });
    $dropdown.append(itemEl);
  });

  $dropdown.show();
}

function highlightDropdownItem() {
  const $items = $('.github-topic-dropdown-item');
  $items.removeClass('active');
  $items.eq(zoneDropdownActiveIndex).addClass('active');
  const activeEl = $items[zoneDropdownActiveIndex];
  if (activeEl) {
    activeEl.scrollIntoView({ block: 'nearest' });
  }
}

function selectZoneTag(tag) {
  const cleanTag = tag.trim().toLowerCase();
  if (cleanTag && !currentModalSelectedZones.includes(cleanTag)) {
    currentModalSelectedZones.push(cleanTag);
  }
  $('#sensorZoneNewInput').val('');
  $('#zoneAutocompleteDropdown').hide();
  renderZoneTagSelector();
  $('#sensorZoneNewInput').focus();
}

function removeZoneTag(tag) {
  currentModalSelectedZones = currentModalSelectedZones.filter(z => z !== tag);
  renderZoneTagSelector();
  $('#sensorZoneNewInput').focus();
}

function renderSensorTypeDropdown(selectedType) {
  const $select = $('#sensorTypeSelect');
  $select.empty();

  activeSensorTypes.forEach(st => {
    const isSelected = st.type === selectedType;
    $select.append(`<option value="${st.type}" ${isSelected ? 'selected' : ''}>${st.name || st.type}</option>`);
  });

  $select.off('change').on('change', function() {
    renderDynamicSensorFields($(this).val());
  });
}

function renderDynamicSensorFields(sensorType, existingValues = {}) {
  const $container = $('#sensorDynamicFields');
  $container.empty();

  const typeMeta = activeSensorTypes.find(t => t.type === sensorType);
  if (!typeMeta || !typeMeta.fields) return;

  if (sensorType === 'Hikvision') {
    const discoHtml = `
      <div class="form-group full-width" style="background: rgba(99, 102, 241, 0.08); border: 1px dashed rgba(99, 102, 241, 0.3); border-radius: var(--radius-sm); padding: 12px; margin-bottom: 8px;">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
          <div>
            <div style="font-weight: 600; font-size: 0.88rem; color: #c7d2fe;">🎥 Hikvision Sensor Discovery</div>
            <div style="font-size: 0.78rem; color: var(--text-secondary);">Query camera/NVR via ISAPI to automatically discover detection channels & sensors</div>
          </div>
          <button type="button" class="btn-primary-action" id="btnHikvisionDiscover" onclick="discoverHikvisionSensors()" style="width: auto; padding: 6px 14px; font-size: 0.8rem; background: var(--color-primary);">
            <span>🔍</span> Connect & Discover
          </button>
        </div>
        <div id="hikvisionDiscoveryStatus" style="margin-top: 8px; font-size: 0.8rem; display: none;"></div>
      </div>
    `;
    $container.append(discoHtml);
  }

  typeMeta.fields.forEach(f => {
    const rawVal = existingValues[f.name] !== undefined ? existingValues[f.name] : (f.default !== undefined ? f.default : '');
    const fieldId = `sensor_f_${f.name}`;

    if (f.type === 'pin') {
      const pinSelect = $(`
        <div class="form-group">
          <label class="form-label">${f.label}</label>
          <select class="form-control" id="${fieldId}"></select>
          <span class="form-help">${f.help || 'Select a free Raspberry Pi BCM GPIO pin'}</span>
        </div>
      `);
      $container.append(pinSelect);
      const $sel = $(`#${fieldId}`);
      const currentModalSensorId = $('#sensorModalId').val();
      renderPinSelectOptions($sel, rawVal, currentModalSensorId);
    } else if (f.type === 'boolean') {
      const isChecked = rawVal === true || rawVal === 'true' || rawVal === 1 || rawVal === '1';
      const onText = f.name === 'invert' ? 'Normally Open (N.O.)' : 'Enabled';
      const offText = f.name === 'invert' ? 'Normally Closed (N.C.)' : 'Disabled';
      $container.append(`
        <div class="form-group">
          <label class="form-label">${f.label}</label>
          <div style="display: flex; align-items: center; gap: 12px; margin-top: 6px;">
            <label class="switch">
              <input type="checkbox" id="${fieldId}" ${isChecked ? 'checked' : ''}>
              <span class="slider"></span>
            </label>
            <span class="switch-status-text" id="${fieldId}_status" style="font-size: 0.85rem; color: var(--text-secondary); font-weight: 500;">
              ${isChecked ? onText : offText}
            </span>
          </div>
          ${f.help ? `<span class="form-help" style="margin-top: 6px;">${f.help}</span>` : ''}
        </div>
      `);
      $(`#${fieldId}`).on('change', function() {
        const checked = $(this).is(':checked');
        $(`#${fieldId}_status`).text(checked ? onText : offText);
      });
    } else if (f.type === 'select') {
      let optionsHtml = '';
      (f.options || []).forEach(opt => {
        const optVal = typeof opt === 'object' ? opt.value : opt;
        const optLabel = typeof opt === 'object' ? opt.label : opt;
        const isSelected = String(rawVal) === String(optVal);
        optionsHtml += `<option value="${optVal}" ${isSelected ? 'selected' : ''}>${optLabel}</option>`;
      });
      $container.append(`
        <div class="form-group">
          <label class="form-label">${f.label}</label>
          <select class="form-control" id="${fieldId}">${optionsHtml}</select>
          ${f.help ? `<span class="form-help">${f.help}</span>` : ''}
        </div>
      `);
    } else if (f.type === 'number') {
      $container.append(`
        <div class="form-group">
          <label class="form-label">${f.label}</label>
          <input type="number" step="any" class="form-control" id="${fieldId}" value="${rawVal !== undefined && rawVal !== '' ? rawVal : (f.default !== undefined ? f.default : '')}" placeholder="${f.placeholder || ''}">
          ${f.help ? `<span class="form-help">${f.help}</span>` : ''}
        </div>
      `);
    } else if (f.type === 'password') {
      $container.append(`
        <div class="form-group">
          <label class="form-label">${f.label}</label>
          <input type="password" class="form-control" id="${fieldId}" value="${rawVal}" placeholder="${f.placeholder || ''}">
          ${f.help ? `<span class="form-help">${f.help}</span>` : ''}
        </div>
      `);
    } else {
      $container.append(`
        <div class="form-group">
          <label class="form-label">${f.label}</label>
          <input type="text" class="form-control" id="${fieldId}" value="${rawVal}" placeholder="${f.placeholder || ''}">
          ${f.help ? `<span class="form-help">${f.help}</span>` : ''}
        </div>
      `);
    }
  });
}

function discoverHikvisionSensors() {
  const ip = $('#sensor_f_ip').val() ? $('#sensor_f_ip').val().trim() : '';
  const user = $('#sensor_f_user').val() ? $('#sensor_f_user').val().trim() : '';
  const pwd = $('#sensor_f_pass').val() ? $('#sensor_f_pass').val().trim() : '';

  if (!ip) {
    showToast('Please enter Camera IP address');
    $('#sensor_f_ip').focus();
    return;
  }

  const $btn = $('#btnHikvisionDiscover');
  const $status = $('#hikvisionDiscoveryStatus');
  $btn.prop('disabled', true).html('<span>⏳</span> Connecting...');
  $status.show().html('<span style="color: var(--text-secondary);">Connecting to camera and querying ISAPI channels...</span>');

  $.ajax({
    type: 'POST',
    url: '/api/hikvision/discover',
    contentType: 'application/json',
    data: JSON.stringify({ ip: ip, user: user, pass: pwd }),
    success: function(resp) {
      $btn.prop('disabled', false).html('<span>🔍</span> Connect & Discover');
      const data = typeof resp === 'string' ? JSON.parse(resp) : resp;

      if (data && data.status === 'success') {
        const dev = data.device || {};
        $status.html(`
          <div style="color: #4ade80; font-weight: 600;">
            ✅ Connected to <b>${dev.model || 'Hikvision Device'}</b> (${dev.name || 'Camera'})
          </div>
          <div style="color: var(--text-secondary); font-size: 0.75rem; margin-top: 2px;">
            Found ${data.events ? data.events.length : 0} available sensor streams across ${dev.channels_count || 1} channel(s).
          </div>
        `);

        // Populate event_filter select
        const $eventSelect = $('#sensor_f_event_filter');
        if ($eventSelect.length && data.events && data.events.length > 0) {
          const currentVal = $eventSelect.val();
          $eventSelect.empty();
          data.events.forEach(ev => {
            $eventSelect.append(`<option value="${ev.value}" data-name="${ev.default_name || ''}" data-class="${ev.device_class || 'motion'}">${ev.label}</option>`);
          });
          if (currentVal) $eventSelect.val(currentVal);

          $eventSelect.off('change.hikAuto').on('change.hikAuto', function() {
            const $opt = $(this).find(':selected');
            const defName = $opt.data('name');
            const devClass = $opt.data('class');
            if (defName && (!$('#sensorInputName').val() || $('#sensorInputName').val() === 'Hikvision IP Camera')) {
              $('#sensorInputName').val(defName);
            }
            if (devClass) {
              $('#sensorInputDeviceClass').val(devClass);
            }
          });

          if (!$('#sensorInputName').val() && data.events[0]?.default_name) {
            $('#sensorInputName').val(data.events[0].default_name);
          }
          if (data.events[0]?.device_class) {
            $('#sensorInputDeviceClass').val(data.events[0].device_class);
          }
        }
        showToast(`Connected to ${dev.model || 'Camera'}! ${data.events.length} sensors found.`);
      } else {
        $status.html(`<div style="color: #f87171;">⚠️ ${data.message || 'Connection failed'}</div>`);
        showToast(data.message || 'Failed to connect to camera');
      }
    },
    error: function() {
      $btn.prop('disabled', false).html('<span>🔍</span> Connect & Discover');
      $status.html('<div style="color: #f87171;">⚠️ Network error communicating with camera endpoint</div>');
      showToast('Error connecting to camera');
    }
  });
}

function saveSensorFromModal() {
  const sensorId = $('#sensorModalId').val() || 'undefined';
  const name = $('#sensorInputName').val().trim();
  const deviceClass = $('#sensorInputDeviceClass').val() || 'door';
  const behavior = $('#sensorInputBehavior').val();
  const sensorType = $('#sensorTypeSelect').val();

  if (!name) {
    showToast('Please enter a sensor name');
    return;
  }

  const sensorObj = {
    name: name,
    type: sensorType,
    device_class: deviceClass,
    zones: currentModalSelectedZones,
    behavior: behavior
  };

  const typeMeta = activeSensorTypes.find(t => t.type === sensorType);
  if (typeMeta && typeMeta.fields) {
    typeMeta.fields.forEach(f => {
      const fieldSelector = `#sensor_f_${f.name}`;
      if (f.type === 'boolean') {
        sensorObj[f.name] = $(fieldSelector).is(':checked');
      } else if (f.type === 'pin') {
        sensorObj[f.name] = parseInt($(fieldSelector).val(), 10);
      } else if (f.type === 'number') {
        const rawNum = $(fieldSelector).val();
        sensorObj[f.name] = (rawNum !== '' && !isNaN(parseFloat(rawNum))) ? parseFloat(rawNum) : (f.default !== undefined ? f.default : 0);
      } else {
        sensorObj[f.name] = $(fieldSelector).val();
      }
    });
  }

  const payload = {};
  payload[sensorId] = sensorObj;

  $.ajax({
    type: 'POST',
    url: '/addSensor',
    contentType: 'application/json',
    data: JSON.stringify(payload),
    success: function() {
      showToast('Sensor saved successfully');
      closeAllModals();
      refreshSensors();
    },
    error: function() {
      showToast('Failed to save sensor');
    }
  });
}

function deleteSensor(sensorId) {
  if (confirm(`Are you sure you want to delete this sensor?`)) {
    socket.emit('delSensor', { sensor: sensorId });
    showToast('Sensor deleted');
    closeAllModals();
    refreshSensors();
  }
}

/* ==========================================================================
   Modernized Sensor Visual Timeline Analysis
   ========================================================================== */

function openTimelineModal() {
  $.getJSON('/getSensorsLog.json?type=sensor&format=json&combineSensors=True&limit=0').done(function(data) {
    const groups = new vis.DataSet();
    let sensorCount = 0;
    $.each(allProperties.sensors, function(i, s) {
      sensorCount++;
      groups.add({ id: i, content: s.name || i });
    });

    const items = new vis.DataSet();
    let eventCount = 0;
    if (data && data.log) {
      data.log.forEach((tmplog, idx) => {
        if (tmplog.timeend && tmplog.type && tmplog.type[2]) {
          eventCount++;
          items.add({
            id: idx,
            content: tmplog.timediff || 'Triggered',
            start: tmplog.time,
            end: tmplog.timeend,
            group: tmplog.type[2]
          });
        }
      });
    }

    $('#timelineTotalEvents').text(`Events: ${eventCount}`);
    $('#timelineActiveSensors').text(`Sensors: ${sensorCount}`);

    const container = document.getElementById('timelineContainer');
    $(container).empty();

    const options = {
      stack: false,
      zoomMin: 1000 * 60 * 5, // 5 minutes min zoom
      zoomMax: 1000 * 60 * 60 * 24 * 31, // 1 month max zoom
      orientation: 'top'
    };

    activeTimelineInstance = new vis.Timeline(container, items, groups, options);
    $('#timelineModalBackdrop').css('display', 'flex');
  });
}

function setTimelineWindow(range) {
  if (!activeTimelineInstance) return;
  const now = new Date();
  let start = new Date();

  if (range === '1h') {
    start.setHours(now.getHours() - 1);
  } else if (range === '24h') {
    start.setHours(now.getHours() - 24);
  } else if (range === '7d') {
    start.setDate(now.getDate() - 7);
  }

  activeTimelineInstance.setWindow(start, now, { animation: true });
}

function fitTimelineView() {
  if (activeTimelineInstance) {
    activeTimelineInstance.fit({ animation: true });
  }
}

/* ==========================================================================
   User & System Management
   ========================================================================== */

function changeUser() {
  const newUser = $('#settingsUserSelect').val();
  if (newUser) {
    $.getJSON(`/switchUser?newuser=${encodeURIComponent(newUser)}`).done(function() {
      location.reload();
    });
  }
}

function restartService() {
  if (confirm('Restart AlarmPI background service?')) {
    $.getJSON('/restart').done(function() {
      showToast('Restarting service...');
      setTimeout(() => location.reload(), 3000);
    });
  }
}

function logout() {
  $.getJSON('/logout').done(function() {
    location.href = '/login';
  });
}

function closeAllModals() {
  $('.modal-backdrop').hide();
  $('#zoneAutocompleteDropdown').hide();
}

function showToast(message) {
  const $toast = $(`<div class="toast"><span>🔔</span> ${message}</div>`);
  $('#toastContainer').append($toast);
  setTimeout(() => {
    $toast.fadeOut(400, function() { $(this).remove(); });
  }, 3000);
}
