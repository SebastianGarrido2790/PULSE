/**
 * PULSE — Point-Level Understanding & Strategic Leverage Engine
 * Interactive Presentation Layer (Tactical Cockpit) Controller
 *
 * Authority: Phase 6.5 Decisions D-1, D-2, D-4, D-7
 */

// ============================================================================
// 1. APPLICATION STATE & CONFIGURATION
// ============================================================================

const CONFIG = {
  LEVERAGE_THRESHOLD: 0.05, // tau = 5.0%
  MAX_LEVERAGE_Y_DEFAULT: 0.20, // 20% default top of chart
  PADDING: { top: 25, right: 30, bottom: 30, left: 45 },
  TENNIS_POINT_MAP: ["0", "15", "30", "40", "AD"],
};

/**
 * Global Cockpit State Store
 */
const state = {
  matches: [],
  selectedMatchId: null,
  matchMetadata: null,
  eventSource: null,
  isPlaying: false,
  isPaused: false,
  isCompleted: false,
  speedMultiplier: 1.0,
  currentPointIndex: 0,
  totalPoints: 0,
  pointsHistory: [], // Array of point data for canvas timeline
  hoveredPointIndex: null,
};

// ============================================================================
// 2. CANVAS 2D LEVERAGE & CONFIDENCE BAND ENGINE (Stage 3)
// ============================================================================

const canvasEl = document.getElementById("leverage-canvas");
const canvasCtx = canvasEl ? canvasEl.getContext("2d") : null;
const tooltipEl = document.getElementById("canvas-tooltip");

/**
 * Initialize Canvas with High-DPI support
 */
function setupCanvasDPI() {
  if (!canvasEl || !canvasCtx) return;
  const rect = canvasEl.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;

  canvasEl.width = rect.width * dpr;
  canvasEl.height = rect.height * dpr;
  canvasCtx.scale(dpr, dpr);
}

/**
 * Transform data coordinates (point index, leverage value) to canvas pixel coordinates
 */
function getCanvasCoords(pointIdx, value, totalPts, maxY, width, height) {
  const { top, right, bottom, left } = CONFIG.PADDING;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;

  const effectiveTotal = Math.max(totalPts - 1, 10);
  const x = left + (pointIdx / effectiveTotal) * plotWidth;
  const y = top + plotHeight - (Math.max(0, value) / maxY) * plotHeight;

  return { x, y };
}

/**
 * Render the complete Leverage & Momentum Oscillogram
 */
export function renderLeverageChart() {
  if (!canvasEl || !canvasCtx) return;

  const rect = canvasEl.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;

  // Clear Canvas
  canvasCtx.clearRect(0, 0, width, height);

  const { top, right, bottom, left } = CONFIG.PADDING;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;

  const history = state.pointsHistory;
  const totalCount = Math.max(state.totalPoints, history.length, 20);

  // Determine dynamic Y-axis maximum
  let maxY = CONFIG.MAX_LEVERAGE_Y_DEFAULT;
  for (const pt of history) {
    if (pt.wilsonUpper > maxY) maxY = Math.ceil(pt.wilsonUpper * 20) / 20 + 0.05;
    if (pt.deltaLeverage > maxY) maxY = Math.ceil(pt.deltaLeverage * 20) / 20 + 0.05;
  }

  // 1. Draw Grid Lines & Y-Axis Scale
  canvasCtx.strokeStyle = "rgba(255, 255, 255, 0.06)";
  canvasCtx.lineWidth = 1;
  canvasCtx.setLineDash([]);
  canvasCtx.fillStyle = "#9CA3AF";
  canvasCtx.font = "10px ui-monospace, SFMono-Regular, monospace";
  canvasCtx.textAlign = "right";
  canvasCtx.textBaseline = "middle";

  const yTicks = 4;
  for (let i = 0; i <= yTicks; i++) {
    const val = (maxY / yTicks) * i;
    const yPos = top + plotHeight - (val / maxY) * plotHeight;

    canvasCtx.beginPath();
    canvasCtx.moveTo(left, yPos);
    canvasCtx.lineTo(width - right, yPos);
    canvasCtx.stroke();

    canvasCtx.fillText(`${(val * 100).toFixed(0)}%`, left - 8, yPos);
  }

  // 2. Draw Escalation Threshold Line (tau = 5.0%)
  const threshY = top + plotHeight - (CONFIG.LEVERAGE_THRESHOLD / maxY) * plotHeight;
  if (threshY >= top && threshY <= top + plotHeight) {
    canvasCtx.save();
    canvasCtx.strokeStyle = "#F59E0B";
    canvasCtx.lineWidth = 1.5;
    canvasCtx.setLineDash([4, 4]);
    canvasCtx.beginPath();
    canvasCtx.moveTo(left, threshY);
    canvasCtx.lineTo(width - right, threshY);
    canvasCtx.stroke();

    canvasCtx.fillStyle = "#F59E0B";
    canvasCtx.textAlign = "left";
    canvasCtx.fillText("τ = 5.0% Escalation Threshold", width - right - 165, threshY - 7);
    canvasCtx.restore();
  }

  if (history.length === 0) {
    canvasCtx.fillStyle = "rgba(156, 163, 175, 0.35)";
    canvasCtx.font = "12px system-ui, sans-serif";
    canvasCtx.textAlign = "center";
    canvasCtx.fillText("Awaiting point progression stream...", width / 2, height / 2);
    return;
  }

  // 3. Draw Shaded Wilson 95% Confidence Interval Band Envelope
  if (history.length > 1) {
    canvasCtx.save();
    canvasCtx.beginPath();

    // Top curve: Wilson Upper Bound (Left to Right)
    for (let i = 0; i < history.length; i++) {
      const pt = history[i];
      const { x, y } = getCanvasCoords(i, pt.wilsonUpper, totalCount, maxY, width, height);
      if (i === 0) canvasCtx.moveTo(x, y);
      else canvasCtx.lineTo(x, y);
    }

    // Bottom curve: Wilson Lower Bound (Right to Left)
    for (let i = history.length - 1; i >= 0; i--) {
      const pt = history[i];
      const { x, y } = getCanvasCoords(i, pt.wilsonLower, totalCount, maxY, width, height);
      canvasCtx.lineTo(x, y);
    }

    canvasCtx.closePath();
    canvasCtx.fillStyle = "rgba(16, 185, 129, 0.15)";
    canvasCtx.fill();
    canvasCtx.restore();
  }

  // 4. Draw Delta Leverage (ΔL) Continuous Spline
  canvasCtx.save();
  canvasCtx.strokeStyle = "#10B981";
  canvasCtx.lineWidth = 2.5;
  canvasCtx.lineJoin = "round";
  canvasCtx.lineCap = "round";
  canvasCtx.shadowColor = "rgba(16, 185, 129, 0.4)";
  canvasCtx.shadowBlur = 6;
  canvasCtx.beginPath();

  for (let i = 0; i < history.length; i++) {
    const pt = history[i];
    const { x, y } = getCanvasCoords(i, pt.deltaLeverage, totalCount, maxY, width, height);
    if (i === 0) canvasCtx.moveTo(x, y);
    else canvasCtx.lineTo(x, y);
  }
  canvasCtx.stroke();
  canvasCtx.restore();

  // 5. Draw Escalated Point Markers & Current Head Cursor
  for (let i = 0; i < history.length; i++) {
    const pt = history[i];
    const { x, y } = getCanvasCoords(i, pt.deltaLeverage, totalCount, maxY, width, height);

    if (pt.isEscalated) {
      canvasCtx.save();
      canvasCtx.fillStyle = "#EF4444";
      canvasCtx.strokeStyle = "#FFFFFF";
      canvasCtx.lineWidth = 1.5;
      canvasCtx.shadowColor = "rgba(239, 68, 68, 0.6)";
      canvasCtx.shadowBlur = 8;
      canvasCtx.beginPath();
      canvasCtx.arc(x, y, 4, 0, Math.PI * 2);
      canvasCtx.fill();
      canvasCtx.stroke();
      canvasCtx.restore();
    }

    // Active point scanning head
    if (i === history.length - 1) {
      canvasCtx.save();
      canvasCtx.fillStyle = "#10B981";
      canvasCtx.strokeStyle = "#FFFFFF";
      canvasCtx.lineWidth = 2;
      canvasCtx.beginPath();
      canvasCtx.arc(x, y, 5, 0, Math.PI * 2);
      canvasCtx.fill();
      canvasCtx.stroke();
      canvasCtx.restore();
    }
  }
}

/**
 * Handle Canvas Mouse Move for Dynamic Hover Tooltip
 */
function handleCanvasMouseMove(e) {
  if (!canvasEl || !tooltipEl || state.pointsHistory.length === 0) return;

  const rect = canvasEl.getBoundingClientRect();
  const mouseX = e.clientX - rect.left;
  const mouseY = e.clientY - rect.top;

  const { top, right, bottom, left } = CONFIG.PADDING;
  const plotWidth = rect.width - left - right;
  const totalCount = Math.max(state.totalPoints, state.pointsHistory.length, 20);

  if (mouseX < left || mouseX > rect.width - right) {
    tooltipEl.classList.add("hidden");
    state.hoveredPointIndex = null;
    return;
  }

  const relativeX = (mouseX - left) / plotWidth;
  const closestIdx = Math.round(relativeX * (totalCount - 1));

  if (closestIdx >= 0 && closestIdx < state.pointsHistory.length) {
    const pt = state.pointsHistory[closestIdx];
    state.hoveredPointIndex = closestIdx;

    tooltipEl.innerHTML = `
      <div style="font-weight:700; margin-bottom:2px;">Point #${pt.pointIndex + 1} (${pt.score})</div>
      <div style="color:#10B981;">ΔL: ${(pt.deltaLeverage * 100).toFixed(2)}%</div>
      <div style="color:#9CA3AF; font-size:0.7rem;">95% CI: [${(pt.wilsonLower * 100).toFixed(1)}%, ${(pt.wilsonUpper * 100).toFixed(1)}%]</div>
      ${pt.isEscalated ? '<div style="color:#EF4444; font-weight:700; margin-top:2px;">⚡ Escalation Fired</div>' : ""}
    `;

    tooltipEl.style.left = `${mouseX}px`;
    tooltipEl.style.top = `${mouseY - 10}px`;
    tooltipEl.classList.remove("hidden");
  } else {
    tooltipEl.classList.add("hidden");
    state.hoveredPointIndex = null;
  }
}

function handleCanvasMouseLeave() {
  if (tooltipEl) tooltipEl.classList.add("hidden");
  state.hoveredPointIndex = null;
}

if (canvasEl) {
  canvasEl.addEventListener("mousemove", handleCanvasMouseMove);
  canvasEl.addEventListener("mouseleave", handleCanvasMouseLeave);
}
window.addEventListener("resize", () => {
  setupCanvasDPI();
  renderLeverageChart();
});

// ============================================================================
// 3. SCORE & FORMATTING HELPERS
// ============================================================================

function formatTennisPoint(serverScore, returnerScore) {
  const map = CONFIG.TENNIS_POINT_MAP;
  const sStr = map[serverScore] || String(serverScore);
  const rStr = map[returnerScore] || String(returnerScore);

  if (serverScore >= 3 && returnerScore >= 3) {
    if (serverScore === returnerScore) return { p1: "40", p2: "40" };
    if (serverScore > returnerScore) return { p1: "AD", p2: "40" };
    return { p1: "40", p2: "AD" };
  }
  return { p1: sStr, p2: rStr };
}

// ============================================================================
// 4. SSE EVENT CONSUMPTION & REACTIVE UI CONTROLLER (Stage 4)
// ============================================================================

const DOM = {
  matchSelect: document.getElementById("match-select"),
  matchTitle: document.getElementById("match-title"),
  surfaceBadge: document.getElementById("match-surface-badge"),
  streamStatusBadge: document.getElementById("stream-status-badge"),
  streamStatusText: document.getElementById("stream-status-text"),
  otelTraceBadge: document.getElementById("otel-trace-badge"),
  traceIdVal: document.getElementById("trace-id-val"),
  highLeverageBadge: document.getElementById("high-leverage-badge"),
  namePlayerP1: document.getElementById("name-player-p1"),
  namePlayerP2: document.getElementById("name-player-p2"),
  serverIndicatorP1: document.getElementById("server-indicator-p1"),
  serverIndicatorP2: document.getElementById("server-indicator-p2"),
  scoreSetsP1: document.getElementById("score-sets-p1"),
  scoreSetsP2: document.getElementById("score-sets-p2"),
  scoreGamesP1: document.getElementById("score-games-p1"),
  scoreGamesP2: document.getElementById("score-games-p2"),
  scorePointsP1: document.getElementById("score-points-p1"),
  scorePointsP2: document.getElementById("score-points-p2"),
  currentPointIdx: document.getElementById("current-point-idx"),
  totalPointsCount: document.getElementById("total-points-count"),
  curPWin: document.getElementById("cur-p-win"),
  curMarkovM: document.getElementById("cur-markov-m"),
  statDeltaLeverage: document.getElementById("stat-delta-leverage"),
  statWilsonCi: document.getElementById("stat-wilson-ci"),
  // Topology Cards & Badges
  nodeStateMonitor: document.getElementById("node-state-monitor"),
  badgeStateMonitor: document.getElementById("badge-state-monitor"),
  latencyStateMonitor: document.getElementById("latency-state-monitor"),
  nodePressureDiagnostic: document.getElementById("node-pressure-diagnostic"),
  badgePressureDiagnostic: document.getElementById("badge-pressure-diagnostic"),
  metricDeltaP: document.getElementById("metric-delta-p"),
  metricShrinkage: document.getElementById("metric-shrinkage"),
  nodeStrategyExploit: document.getElementById("node-strategy-exploit"),
  badgeStrategyExploit: document.getElementById("badge-strategy-exploit"),
  metricSufficiencyGate: document.getElementById("metric-sufficiency-gate"),
  metricEvGain: document.getElementById("metric-ev-gain"),
  nodeTacticalOutput: document.getElementById("node-tactical-output"),
  badgeTacticalOutput: document.getElementById("badge-tactical-output"),
  metricTacticalMode: document.getElementById("metric-tactical-mode"),
  metricGroundedness: document.getElementById("metric-groundedness"),
  // Game Theory Matrix & Exploit
  cellWideWide: document.getElementById("cell-wide-wide"),
  cellWideT: document.getElementById("cell-wide-t"),
  cellTWide: document.getElementById("cell-t-wide"),
  cellTT: document.getElementById("cell-t-t"),
  barNash: document.getElementById("bar-nash"),
  barBias: document.getElementById("bar-bias"),
  nashRatioLabel: document.getElementById("nash-ratio-label"),
  biasRatioLabel: document.getElementById("bias-ratio-label"),
  exploitCallout: document.getElementById("exploit-callout"),
  exploitRecText: document.getElementById("exploit-recommendation-text"),
  // Tactical Feed
  tacticalHeadline: document.getElementById("tactical-headline"),
  tacticalNarrative: document.getElementById("tactical-narrative"),
  tacticalRecList: document.getElementById("tactical-recommendation-list"),
  // Control Buttons
  btnPlay: document.getElementById("btn-play"),
  btnPlayText: document.getElementById("btn-play-text"),
  btnPause: document.getElementById("btn-pause"),
  btnReset: document.getElementById("btn-reset"),
  speedSelector: document.getElementById("speed-select"),
};

/**
 * 16a. Fetch and populate available match list
 */
export async function initMatchList() {
  try {
    const res = await fetch("/v1/matches");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.matches = data.matches || [];

    if (!DOM.matchSelect) return;
    DOM.matchSelect.innerHTML = "";

    if (state.matches.length === 0) {
      DOM.matchSelect.innerHTML = "<option value='' disabled>No matches available</option>";
      return;
    }

    state.matches.forEach((mId, idx) => {
      const opt = document.createElement("option");
      opt.value = mId;
      opt.textContent = mId.replace(/_/g, " ");
      if (idx === 0) opt.selected = true;
      DOM.matchSelect.appendChild(opt);
    });

    // Load first match metadata by default
    state.selectedMatchId = state.matches[0];
    await loadMatchMetadata(state.selectedMatchId);
  } catch (err) {
    console.error("Failed to load match list:", err);
    if (DOM.matchTitle) DOM.matchTitle.textContent = "Error loading match catalogue";
  }
}

/**
 * 16b. Fetch and render match metadata
 */
export async function loadMatchMetadata(matchId) {
  try {
    const res = await fetch(`/v1/matches/${encodeURIComponent(matchId)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const meta = await res.json();
    state.matchMetadata = meta;
    state.totalPoints = meta.total_points || 0;

    // Update Header and Scoreboard metadata
    if (DOM.matchTitle) DOM.matchTitle.textContent = `${meta.server_p1} vs ${meta.returner_p2}`;
    if (DOM.surfaceBadge) DOM.surfaceBadge.textContent = `Surface: ${meta.surface}`;
    if (DOM.namePlayerP1) DOM.namePlayerP1.textContent = meta.server_p1;
    if (DOM.namePlayerP2) DOM.namePlayerP2.textContent = meta.returner_p2;
    if (DOM.totalPointsCount) DOM.totalPointsCount.textContent = String(meta.total_points);

    resetUIState();
  } catch (err) {
    console.error(`Failed to load metadata for match ${matchId}:`, err);
  }
}

/**
 * Reset all UI components to initial clean state
 */
export function resetUIState() {
  state.pointsHistory = [];
  state.currentPointIndex = 0;
  state.isCompleted = false;

  if (DOM.currentPointIdx) DOM.currentPointIdx.textContent = "0";
  if (DOM.curPWin) DOM.curPWin.textContent = "50.0%";
  if (DOM.curMarkovM) DOM.curMarkovM.textContent = "50.0%";
  if (DOM.statDeltaLeverage) DOM.statDeltaLeverage.textContent = "0.00%";
  if (DOM.statWilsonCi) DOM.statWilsonCi.textContent = "[0.00%, 0.00%]";

  if (DOM.scoreSetsP1) DOM.scoreSetsP1.textContent = "0";
  if (DOM.scoreSetsP2) DOM.scoreSetsP2.textContent = "0";
  if (DOM.scoreGamesP1) DOM.scoreGamesP1.textContent = "0";
  if (DOM.scoreGamesP2) DOM.scoreGamesP2.textContent = "0";
  if (DOM.scorePointsP1) DOM.scorePointsP1.textContent = "0";
  if (DOM.scorePointsP2) DOM.scorePointsP2.textContent = "0";

  if (DOM.serverIndicatorP1) DOM.serverIndicatorP1.classList.remove("hidden");
  if (DOM.serverIndicatorP2) DOM.serverIndicatorP2.classList.add("hidden");

  if (DOM.highLeverageBadge) {
    DOM.highLeverageBadge.textContent = "Standard Leverage";
    DOM.highLeverageBadge.className = "badge badge-leverage";
  }

  // Reset Topology Badges
  resetTopologyBadges();

  // Reset Game Theory Panel
  if (DOM.exploitCallout) DOM.exploitCallout.classList.add("hidden");
  if (DOM.barNash) DOM.barNash.style.width = "50%";
  if (DOM.barBias) DOM.barBias.style.width = "50%";
  if (DOM.nashRatioLabel) DOM.nashRatioLabel.textContent = "50% Wide / 50% T";
  if (DOM.biasRatioLabel) DOM.biasRatioLabel.textContent = "50% Wide / 50% T";

  const cells = [DOM.cellWideWide, DOM.cellWideT, DOM.cellTWide, DOM.cellTT];
  cells.forEach((c) => {
    if (c) {
      c.textContent = "0.00";
      c.classList.remove("highlight-best");
    }
  });

  // Reset Tactical Feed
  if (DOM.tacticalHeadline) DOM.tacticalHeadline.textContent = "Awaiting match stream initialization...";
  if (DOM.tacticalNarrative) {
    DOM.tacticalNarrative.textContent =
      'Click "Start Replay" to observe continuous point leverage tracking and conditional agent execution.';
  }
  if (DOM.tacticalRecList) {
    DOM.tacticalRecList.innerHTML = "<li>System is in standby mode. Ready to receive point stream.</li>";
  }

  renderLeverageChart();
}

function resetTopologyBadges() {
  const setNode = (node, badge, status, text) => {
    if (node) {
      node.classList.remove("node-active", "node-fired");
    }
    if (badge) {
      badge.className = `node-status-pill ${status}`;
      badge.textContent = text;
    }
  };

  setNode(DOM.nodeStateMonitor, DOM.badgeStateMonitor, "status-idle", "IDLE");
  setNode(DOM.nodePressureDiagnostic, DOM.badgePressureDiagnostic, "status-idle", "IDLE");
  setNode(DOM.nodeStrategyExploit, DOM.badgeStrategyExploit, "status-idle", "IDLE");
  setNode(DOM.nodeTacticalOutput, DOM.badgeTacticalOutput, "status-idle", "IDLE");

  if (DOM.latencyStateMonitor) DOM.latencyStateMonitor.textContent = "--";
  if (DOM.metricDeltaP) DOM.metricDeltaP.textContent = "--";
  if (DOM.metricShrinkage) DOM.metricShrinkage.textContent = "--";
  if (DOM.metricSufficiencyGate) DOM.metricSufficiencyGate.textContent = "N/A";
  if (DOM.metricEvGain) DOM.metricEvGain.textContent = "--";
  if (DOM.metricTacticalMode) DOM.metricTacticalMode.textContent = "Passthrough";
  if (DOM.metricGroundedness) DOM.metricGroundedness.textContent = "100%";
}

/**
 * 17. Start or Resume SSE Replay Stream
 */
export function startStream() {
  if (!state.selectedMatchId) return;

  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }

  state.isPlaying = true;
  state.isPaused = false;
  state.isCompleted = false;

  updateControlsState();

  const url = `/v1/matches/${encodeURIComponent(state.selectedMatchId)}/stream?speed_multiplier=${state.speedMultiplier}`;
  state.eventSource = new EventSource(url);

  if (DOM.streamStatusBadge) {
    DOM.streamStatusBadge.className = "badge badge-live streaming";
    if (DOM.streamStatusText) DOM.streamStatusText.textContent = "Live Replay";
  }

  state.eventSource.onmessage = (event) => {
    if (!event.data) return;
    try {
      const data = JSON.parse(event.data);
      handlePointEvent(data);
    } catch (err) {
      console.error("Error parsing SSE event payload:", err, event.data);
    }
  };

  state.eventSource.onerror = (err) => {
    console.warn("SSE connection closed or ended:", err);
    if (state.eventSource) {
      state.eventSource.close();
      state.eventSource = null;
    }
    state.isPlaying = false;

    if (DOM.streamStatusBadge) {
      if (state.isCompleted) {
        DOM.streamStatusBadge.className = "badge badge-live";
        if (DOM.streamStatusText) DOM.streamStatusText.textContent = "Completed";
      } else {
        DOM.streamStatusBadge.className = "badge badge-live paused";
        if (DOM.streamStatusText) DOM.streamStatusText.textContent = "Stream Ended";
      }
    }
    updateControlsState();
  };
}

/**
 * Pause active stream
 */
export function pauseStream() {
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }
  state.isPlaying = false;
  state.isPaused = true;

  if (DOM.streamStatusBadge) {
    DOM.streamStatusBadge.className = "badge badge-live paused";
    if (DOM.streamStatusText) DOM.streamStatusText.textContent = "Paused";
  }
  updateControlsState();
}

/**
 * Reset active stream back to start
 */
export function resetStream() {
  pauseStream();
  resetUIState();
  updateControlsState();
}

/**
 * Update button states according to playback mode
 */
function updateControlsState() {
  if (DOM.btnPlay) {
    DOM.btnPlay.disabled = state.isPlaying;
    if (DOM.btnPlayText) DOM.btnPlayText.textContent = state.isPaused ? "Resume" : "Start Replay";
  }
  if (DOM.btnPause) {
    DOM.btnPause.disabled = !state.isPlaying;
  }
  if (DOM.btnReset) {
    DOM.btnReset.disabled = !state.isPlaying && !state.isPaused && state.pointsHistory.length === 0;
  }
  if (DOM.matchSelect) {
    DOM.matchSelect.disabled = state.isPlaying;
  }
}

/**
 * 18. Wire incoming StreamPointEvent to all reactive sub-components
 */
export function handlePointEvent(ev) {
  if (ev.event_type === "complete") {
    state.isCompleted = true;
    if (DOM.streamStatusBadge) {
      DOM.streamStatusBadge.className = "badge badge-live";
      if (DOM.streamStatusText) DOM.streamStatusText.textContent = "Match Complete";
    }
    if (DOM.tacticalHeadline) DOM.tacticalHeadline.textContent = "🏁 Match Stream Finished";
    if (DOM.tacticalNarrative) DOM.tacticalNarrative.textContent = "All charted points have been streamed and evaluated.";
    pauseStream();
    return;
  }

  if (ev.event_type !== "point") return;

  const ctx = ev.point_context;
  const lev = ev.leverage_result || {};
  const pressure = ev.pressure_result;
  const exploit = ev.exploit_result;
  const tactical = ev.tactical_output;
  const decLog = ev.decision_log || [];

  // 1. Update Scoreboard
  if (ctx) {
    if (DOM.currentPointIdx) DOM.currentPointIdx.textContent = String(ev.point_index + 1);

    // Sets & Games
    if (DOM.scoreSetsP1) DOM.scoreSetsP1.textContent = String(ctx.set_score_server);
    if (DOM.scoreSetsP2) DOM.scoreSetsP2.textContent = String(ctx.set_score_returner);
    if (DOM.scoreGamesP1) DOM.scoreGamesP1.textContent = String(ctx.game_score_server);
    if (DOM.scoreGamesP2) DOM.scoreGamesP2.textContent = String(ctx.game_score_returner);

    // Point Scores
    const pts = formatTennisPoint(ctx.point_score_server, ctx.point_score_returner);
    if (DOM.scorePointsP1) DOM.scorePointsP1.textContent = pts.p1;
    if (DOM.scorePointsP2) DOM.scorePointsP2.textContent = pts.p2;

    // Server ball indicator (P1 vs P2)
    const isP1Serving = ctx.server_id === state.matchMetadata?.server_p1;
    if (DOM.serverIndicatorP1 && DOM.serverIndicatorP2) {
      if (isP1Serving) {
        DOM.serverIndicatorP1.classList.remove("hidden");
        DOM.serverIndicatorP2.classList.add("hidden");
      } else {
        DOM.serverIndicatorP1.classList.add("hidden");
        DOM.serverIndicatorP2.classList.remove("hidden");
      }
    }
  }

  // Model & Solver Probabilities
  const pWin = lev.p_hat !== undefined ? (lev.p_hat * 100).toFixed(1) + "%" : "--";
  if (DOM.curPWin) DOM.curPWin.textContent = pWin;

  const deltaL = lev.delta_leverage || 0.0;
  const isEscalated = deltaL >= CONFIG.LEVERAGE_THRESHOLD;

  if (DOM.statDeltaLeverage) DOM.statDeltaLeverage.textContent = `${(deltaL * 100).toFixed(2)}%`;
  if (DOM.statWilsonCi) {
    const low = lev.delta_leverage_low !== undefined ? (lev.delta_leverage_low * 100).toFixed(1) : "0.0";
    const high = lev.delta_leverage_high !== undefined ? (lev.delta_leverage_high * 100).toFixed(1) : "0.0";
    DOM.statWilsonCi.textContent = `[${low}%, ${high}%]`;
  }

  // High Leverage Badge
  if (DOM.highLeverageBadge) {
    if (deltaL >= 0.10) {
      DOM.highLeverageBadge.textContent = "⚡ CRITICAL LEVERAGE";
      DOM.highLeverageBadge.className = "badge badge-leverage critical";
    } else if (deltaL >= CONFIG.LEVERAGE_THRESHOLD) {
      DOM.highLeverageBadge.textContent = "⚠ ELEVATED LEVERAGE";
      DOM.highLeverageBadge.className = "badge badge-leverage elevated";
    } else {
      DOM.highLeverageBadge.textContent = "Standard Leverage";
      DOM.highLeverageBadge.className = "badge badge-leverage";
    }
  }

  // 2. Append Point to Canvas Oscillogram
  const pointRecord = {
    pointIndex: ev.point_index,
    score: ctx ? `${ctx.point_score_server}-${ctx.point_score_returner}` : "0-0",
    deltaLeverage: deltaL,
    wilsonLower: lev.delta_leverage_low !== undefined ? lev.delta_leverage_low : deltaL,
    wilsonUpper: lev.delta_leverage_high !== undefined ? lev.delta_leverage_high : deltaL,
    isEscalated,
  };
  state.pointsHistory.push(pointRecord);
  state.currentPointIndex = ev.point_index;
  renderLeverageChart();

  // 3. Update Topology Cards
  updateTopologyUI(decLog, pressure, exploit, tactical);

  // 4. Update Game Theory Exploit Panel
  updateGameTheoryUI(exploit);

  // 5. Update Tactical Advisory Feed
  updateTacticalFeedUI(tactical, deltaL);

  // 6. Update OTel Trace Context Badge
  if (DOM.traceIdVal) {
    DOM.traceIdVal.textContent = `trace: pt-${ev.point_index}-${ev.match_id.substring(0, 8)}`;
  }
}

/**
 * Reactive Topology Inspector Updates
 */
function updateTopologyUI(decisionLog, pressureResult, exploitResult, tacticalOutput) {
  // StateMonitorNode: Always ACTIVE
  if (DOM.nodeStateMonitor && DOM.badgeStateMonitor) {
    DOM.nodeStateMonitor.classList.add("node-active");
    DOM.badgeStateMonitor.className = "node-status-pill status-active";
    DOM.badgeStateMonitor.textContent = "ACTIVE";
    if (DOM.latencyStateMonitor) DOM.latencyStateMonitor.textContent = "< 5ms";
  }

  // PressureDiagnosticNode
  if (DOM.nodePressureDiagnostic && DOM.badgePressureDiagnostic) {
    if (pressureResult) {
      DOM.nodePressureDiagnostic.classList.add("node-fired");
      DOM.badgePressureDiagnostic.className = "node-status-pill status-fired";
      DOM.badgePressureDiagnostic.textContent = "FIRED";
      if (DOM.metricDeltaP) DOM.metricDeltaP.textContent = `${(pressureResult.delta_p_shrunk * 100).toFixed(1)}%`;
      if (DOM.metricShrinkage) DOM.metricShrinkage.textContent = `${(pressureResult.shrinkage_factor * 100).toFixed(0)}%`;
    } else {
      DOM.nodePressureDiagnostic.classList.remove("node-fired");
      DOM.badgePressureDiagnostic.className = "node-status-pill status-suppressed";
      DOM.badgePressureDiagnostic.textContent = "SUPPRESSED";
      if (DOM.metricDeltaP) DOM.metricDeltaP.textContent = "0.0%";
      if (DOM.metricShrinkage) DOM.metricShrinkage.textContent = "N/A";
    }
  }

  // StrategyExploitNode
  if (DOM.nodeStrategyExploit && DOM.badgeStrategyExploit) {
    if (exploitResult) {
      if (exploitResult.sufficient_data) {
        DOM.nodeStrategyExploit.classList.add("node-fired");
        DOM.badgeStrategyExploit.className = "node-status-pill status-fired";
        DOM.badgeStrategyExploit.textContent = "FIRED";
        if (DOM.metricSufficiencyGate) DOM.metricSufficiencyGate.textContent = `N=${exploitResult.n_opp_total} (PASS)`;
        if (DOM.metricEvGain) DOM.metricEvGain.textContent = `+${((exploitResult.delta || 0) * 100).toFixed(1)}%`;
      } else {
        DOM.nodeStrategyExploit.classList.remove("node-fired");
        DOM.badgeStrategyExploit.className = "node-status-pill status-insufficient";
        DOM.badgeStrategyExploit.textContent = "INSUFFICIENT DATA";
        if (DOM.metricSufficiencyGate) DOM.metricSufficiencyGate.textContent = `N < 10 (GATED)`;
        if (DOM.metricEvGain) DOM.metricEvGain.textContent = "Gated";
      }
    } else {
      DOM.nodeStrategyExploit.classList.remove("node-fired");
      DOM.badgeStrategyExploit.className = "node-status-pill status-suppressed";
      DOM.badgeStrategyExploit.textContent = "SUPPRESSED";
      if (DOM.metricSufficiencyGate) DOM.metricSufficiencyGate.textContent = "N/A";
      if (DOM.metricEvGain) DOM.metricEvGain.textContent = "--";
    }
  }

  // TacticalOutputNode
  if (DOM.nodeTacticalOutput && DOM.badgeTacticalOutput) {
    if (tacticalOutput) {
      DOM.nodeTacticalOutput.classList.add("node-active");
      DOM.badgeTacticalOutput.className = "node-status-pill status-active";
      DOM.badgeTacticalOutput.textContent = tacticalOutput.is_llm_fallback ? "PASSTHROUGH" : "LLM SYNTHESIS";
      if (DOM.metricTacticalMode) DOM.metricTacticalMode.textContent = tacticalOutput.is_llm_fallback ? "Raw Signal" : "LLM Grounded";
      if (DOM.metricGroundedness) DOM.metricGroundedness.textContent = "100%";
    }
  }
}

/**
 * Reactive Game Theory Panel Updates
 */
function updateGameTheoryUI(exploitResult) {
  if (!exploitResult || !exploitResult.payoff_matrix) {
    if (DOM.exploitCallout) DOM.exploitCallout.classList.add("hidden");
    return;
  }

  const matrix = exploitResult.payoff_matrix.matrix;
  if (matrix && matrix.length >= 2 && matrix[0].length >= 2) {
    if (DOM.cellWideWide) DOM.cellWideWide.textContent = (matrix[0][0] * 100).toFixed(0) + "%";
    if (DOM.cellWideT) DOM.cellWideT.textContent = (matrix[0][1] * 100).toFixed(0) + "%";
    if (DOM.cellTWide) DOM.cellTWide.textContent = (matrix[1][0] * 100).toFixed(0) + "%";
    if (DOM.cellTT) DOM.cellTT.textContent = (matrix[1][1] * 100).toFixed(0) + "%";

    // Highlight Best Response Action
    const bestAction = exploitResult.best_response_action || "Wide";
    if (bestAction.includes("Wide")) {
      DOM.cellWideWide?.classList.add("highlight-best");
      DOM.cellWideT?.classList.add("highlight-best");
      DOM.cellTWide?.classList.remove("highlight-best");
      DOM.cellTT?.classList.remove("highlight-best");
    } else {
      DOM.cellTWide?.classList.add("highlight-best");
      DOM.cellTT?.classList.add("highlight-best");
      DOM.cellWideWide?.classList.remove("highlight-best");
      DOM.cellWideT?.classList.remove("highlight-best");
    }
  }

  // Strategy Mix Bars
  if (exploitResult.server_equilibrium_mix && exploitResult.server_equilibrium_mix.length >= 2) {
    const widePct = (exploitResult.server_equilibrium_mix[0] * 100).toFixed(0);
    const tPct = (exploitResult.server_equilibrium_mix[1] * 100).toFixed(0);
    if (DOM.barNash) DOM.barNash.style.width = `${widePct}%`;
    if (DOM.nashRatioLabel) DOM.nashRatioLabel.textContent = `${widePct}% Wide / ${tPct}% T`;
  }

  if (exploitResult.observed_returner_mix && exploitResult.observed_returner_mix.length >= 2) {
    const wideBiasPct = (exploitResult.observed_returner_mix[0] * 100).toFixed(0);
    const tBiasPct = (exploitResult.observed_returner_mix[1] * 100).toFixed(0);
    if (DOM.barBias) DOM.barBias.style.width = `${wideBiasPct}%`;
    if (DOM.biasRatioLabel) DOM.biasRatioLabel.textContent = `${wideBiasPct}% Wide / ${tBiasPct}% T`;
  }

  // Exploit Callout Badge
  if (exploitResult.sufficient_data && exploitResult.delta && exploitResult.delta > 0) {
    if (DOM.exploitCallout && DOM.exploitRecText) {
      DOM.exploitRecText.textContent = `+${(exploitResult.delta * 100).toFixed(1)}% EV on Serve ${exploitResult.best_response_action || "Wide"}`;
      DOM.exploitCallout.classList.remove("hidden");
    }
  } else {
    if (DOM.exploitCallout) DOM.exploitCallout.classList.add("hidden");
  }
}

/**
 * Reactive Tactical Advisory Feed Updates
 */
function updateTacticalFeedUI(tacticalOutput, deltaLeverage) {
  if (!tacticalOutput) return;

  if (DOM.tacticalHeadline) {
    if (deltaLeverage >= 0.10) {
      DOM.tacticalHeadline.textContent = "⚡ Critical Tactical Leverage Escalation";
    } else if (deltaLeverage >= CONFIG.LEVERAGE_THRESHOLD) {
      DOM.tacticalHeadline.textContent = "⚠ Elevated Leverage — Strategic Pivot Alert";
    } else {
      DOM.tacticalHeadline.textContent = "Match Rhythm Normal — Standard Point";
    }
  }

  if (DOM.tacticalNarrative) {
    DOM.tacticalNarrative.textContent = tacticalOutput.narrative || "No narrative synthesis generated.";
  }

  if (DOM.tacticalRecList) {
    const raw = tacticalOutput.raw_payload || {};
    DOM.tacticalRecList.innerHTML = "";

    const recs = [];
    if (raw.exploit && raw.exploit.best_response_action) {
      recs.push(`Target Serve: <strong>${raw.exploit.best_response_action}</strong> (+${((raw.exploit.delta || 0) * 100).toFixed(1)}% EV advantage)`);
    }
    if (raw.pressure && raw.pressure.delta_p_shrunk !== undefined) {
      const dev = raw.pressure.delta_p_shrunk;
      if (Math.abs(dev) > 0.02) {
        recs.push(`Pressure Shift: Opponent win probability altered by ${(dev * 100).toFixed(1)}% under leverage.`);
      }
    }
    if (recs.length === 0) {
      recs.push("Maintain baseline high-percentage patterns. Leverage below threshold.");
    }

    recs.forEach((r) => {
      const li = document.createElement("li");
      li.innerHTML = r;
      DOM.tacticalRecList.appendChild(li);
    });
  }
}

// ============================================================================
// 5. EVENT LISTENERS & INITIALIZATION
// ============================================================================

function attachEventListeners() {
  if (DOM.btnPlay) {
    DOM.btnPlay.addEventListener("click", () => {
      startStream();
    });
  }

  if (DOM.btnPause) {
    DOM.btnPause.addEventListener("click", () => {
      pauseStream();
    });
  }

  if (DOM.btnReset) {
    DOM.btnReset.addEventListener("click", () => {
      resetStream();
    });
  }

  if (DOM.matchSelect) {
    DOM.matchSelect.addEventListener("change", async (e) => {
      state.selectedMatchId = e.target.value;
      await loadMatchMetadata(state.selectedMatchId);
    });
  }

  if (DOM.speedSelector) {
    DOM.speedSelector.addEventListener("change", (e) => {
      if (e.target.name === "speed") {
        state.speedMultiplier = parseFloat(e.target.value);
        if (state.isPlaying) {
          // Restart stream with new speed
          startStream();
        }
      }
    });
  }
}

// Bootstrap Application
document.addEventListener("DOMContentLoaded", async () => {
  setupCanvasDPI();
  renderLeverageChart();
  attachEventListeners();
  await initMatchList();
});
