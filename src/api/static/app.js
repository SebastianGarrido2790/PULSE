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
  MIN_POINTS_FOR_CHART: 1,
  PADDING: { top: 25, right: 30, bottom: 30, left: 45 },
};

/**
 * Global Cockpit State
 */
const state = {
  matches: [],
  selectedMatchId: null,
  matchMetadata: null,
  eventSource: null,
  isPlaying: false,
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
    // Empty state watermark
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

  // Find closest point index based on mouse X
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

// Attach Canvas Event Listeners
if (canvasEl) {
  canvasEl.addEventListener("mousemove", handleCanvasMouseMove);
  canvasEl.addEventListener("mouseleave", handleCanvasMouseLeave);
}
window.addEventListener("resize", () => {
  setupCanvasDPI();
  renderLeverageChart();
});

// ============================================================================
// 3. UI REACTIVE UPDATE HELPERS (Scaffolding for Stage 4)
// ============================================================================

export function addPointToHistory(pointEvent) {
  const ctx = pointEvent.point_context;
  const lev = pointEvent.leverage_result || {};
  const isEscalated = (lev.delta_leverage || 0) >= CONFIG.LEVERAGE_THRESHOLD;

  const pointData = {
    pointIndex: pointEvent.point_index,
    score: `${ctx ? ctx.score : "0-0"}`,
    deltaLeverage: lev.delta_leverage || 0.0,
    wilsonLower: lev.wilson_ci_lower !== undefined ? lev.wilson_ci_lower : (lev.delta_leverage || 0),
    wilsonUpper: lev.wilson_ci_upper !== undefined ? lev.wilson_ci_upper : (lev.delta_leverage || 0),
    isEscalated,
  };

  state.pointsHistory.push(pointData);
  state.currentPointIndex = pointEvent.point_index;

  renderLeverageChart();
}

export function resetChartHistory() {
  state.pointsHistory = [];
  state.currentPointIndex = 0;
  renderLeverageChart();
}

// Initial Canvas DPI Setup
document.addEventListener("DOMContentLoaded", () => {
  setupCanvasDPI();
  renderLeverageChart();
});
