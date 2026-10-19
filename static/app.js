/* global window, document, Intl, FormData, URL, crypto */

const DAY_MS = 86_400_000;
const VALID_VIEWS = new Set(["dashboard", "library", "accounts", "models"]);
const VIEW_TITLES = {
  dashboard: "总览",
  library: "日程",
  accounts: "邮箱",
  models: "模型",
};
const WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
const WEEKDAYS_NARROW = ["日", "一", "二", "三", "四", "五", "六"];
const WEEKDAYS_EN = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
const MONTHS_EN = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
const KIND_LABELS = {
  exam: "笔试",
  interview: "面试",
};
const KIND_FILTERS = [
  { id: "all", label: "全部" },
  { id: "exam", label: "笔试" },
  { id: "interview", label: "面试" },
];
const LIBRARY_FILTERS = [
  { id: "all", label: "全部" },
  { id: "upcoming", label: "待参加" },
  { id: "review", label: "待确认" },
  { id: "ended", label: "已结束" },
  { id: "done", label: "已完成" },
  { id: "ignored", label: "已忽略" },
];

const ICONS = {
  arrowRight: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  arrowUpRight: '<path d="M7 17 17 7M8 7h9v9"/>',
  chevronRight: '<path d="m9 18 6-6-6-6"/>',
  chevronDown: '<path d="m6 9 6 6 6-6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  refresh: '<path d="M20 12a8 8 0 1 0-2.34 5.66"/><path d="M20 5v7h-7"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
  clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="15" rx="3"/><path d="M8 3v4M16 3v4M3.5 9.5h17"/>',
  monitor: '<rect x="3" y="4" width="18" height="13" rx="2.5"/><path d="M8 21h8M12 17v4"/>',
  external: '<path d="M13 5h6v6M19 5l-8 8"/><path d="M18 13v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4"/>',
  check: '<path d="m5 12.5 4.2 4.2L19 7"/>',
  checkCircle: '<circle cx="12" cy="12" r="8.5"/><path d="m8.2 12 2.5 2.5 5.2-5.2"/>',
  x: '<path d="m6 6 12 12M18 6 6 18"/>',
  trash: '<path d="M4 7h16M9 7V4.5h6V7M7 7l.7 13h8.6L17 7M10 11v5M14 11v5"/>',
  alert: '<path d="M12 3.8 21 20H3L12 3.8Z"/><path d="M12 9v5M12 17.2v.2"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.1.1l2-2a5 5 0 0 0-7-7l-1.1 1"/><path d="M14 11a5 5 0 0 0-7.1-.1l-2 2a5 5 0 0 0 7 7l1.1-1"/>',
  mapPin: '<path d="M20 10c0 5.4-8 11-8 11S4 15.4 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.6"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="m10.8 12.2 8.7-8.7M16 7l3 3M13.5 9.5l3 3"/>',
  lock: '<rect x="5" y="10" width="14" height="10" rx="2.5"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  eye: '<path d="M2.5 12S6 5.8 12 5.8 21.5 12 21.5 12 18 18.2 12 18.2 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>',
  eyeOff: '<path d="m3 3 18 18"/><path d="M10.6 6.1A10.8 10.8 0 0 1 12 6c6 0 9.5 6 9.5 6a17 17 0 0 1-2.6 3.3M6.6 6.6C3.9 8.5 2.5 12 2.5 12S6 18 12 18c1.2 0 2.3-.2 3.3-.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m4 7 8 6 8-6"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h10"/>',
  sparkle: '<path d="M12 3.5c.6 4.7 3.8 7.9 8.5 8.5-4.7.6-7.9 3.8-8.5 8.5-.6-4.7-3.8-7.9-8.5-8.5 4.7-.6 7.9-3.8 8.5-8.5Z"/>',
  shield: '<path d="M12 3 20 6v5.5c0 4.6-3.4 7.7-8 9.5-4.6-1.8-8-4.9-8-9.5V6l8-3Z"/><path d="m8.6 12 2.2 2.2 4.6-4.6"/>',
  target: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><path d="M12 12h8"/>',
  inbox: '<path d="M4 5h16l1 9H3l1-9Z"/><path d="M3 14v5h18v-5"/><path d="M8 14h8"/>',
  chart: '<path d="M4 19V5M4 19h16"/><path d="m7 15 4-4 3 2 5-6"/>',
  more: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  edit: '<path d="M13.5 6.5 17.5 10.5M5 19l3.8-.8L19.6 7.4a2.1 2.1 0 0 0-3-3L5.8 15.2 5 19Z"/>',
  dot: '<circle cx="12" cy="12" r="4" fill="currentColor" stroke="none"/>',
  form: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="M8 8h8M8 12h8M8 16h5"/>',
  video: '<rect x="3" y="6" width="12" height="12" rx="2.5"/><path d="m15 10 6-3v10l-6-3"/>',
};

const state = {
  view: viewFromLocation(),
  events: [],
  accounts: [],
  providers: [],
  meta: { auto_sync_minutes: 30, demo_count: 0 },
  providerId: "qq",
  libraryFilter: "all",
  kindFilter: "all",
  libraryQuery: "",
  drawer: null,
  drawerCloseTimer: null,
  drawerLastFocus: null,
  reauthAccountId: null,
  syncPollTimer: null,
  syncNotice: false,
  syncFailures: 0,
  accountFormBusy: false,
  aiSettings: {
    active: false,
    has_api_key: false,
    base_url: "",
    model: "",
    max_calls_per_sync: 20,
  },
  aiBusy: false,
  booted: false,
  quickBusy: new Set(),
};

const el = {
  root: document.getElementById("view-root"),
  drawer: document.getElementById("event-drawer"),
  drawerScrim: document.getElementById("drawer-scrim"),
  boot: document.getElementById("boot-screen"),
  toast: document.getElementById("toast-region"),
  sidebar: document.getElementById("sidebar"),
  sidebarBackdrop: document.getElementById("sidebar-backdrop"),
  confirm: document.getElementById("confirm-dialog"),
};

// ---------------------------------------------------------------------------
// Small utilities
// ---------------------------------------------------------------------------

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function safeHttpUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(String(value), window.location.origin);
    if (url.protocol === "http:" || url.protocol === "https:") return url.href;
  } catch {
    return "";
  }
  return "";
}

function icon(name, size = 16, className = "") {
  return `<svg${className ? ` class="${escapeHtml(className)}"` : ""} width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}

function viewFromLocation() {
  const value = window.location.hash.replace(/^#/, "");
  return VALID_VIEWS.has(value) ? value : "dashboard";
}

function providerById(id) {
  return state.providers.find((provider) => provider.id === id) || null;
}

function providerName(id) {
  return providerById(id)?.name || id || "邮箱";
}

function detectProviderId(email) {
  const domain = String(email || "").split("@")[1]?.trim().toLowerCase() || "";
  if (!domain || !domain.includes(".")) return "";
  if (domain === "qq.com" || domain === "foxmail.com") return "qq";
  if (domain === "163.com") return "163";
  if (domain === "126.com") return "126";
  if (domain === "gmail.com" || domain === "googlemail.com") return "gmail";
  return "custom";
}

const beijingFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Shanghai",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

function beijingInfo(value) {
  if (!value) return null;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const values = {};
  for (const part of beijingFormatter.formatToParts(date)) {
    if (part.type !== "literal") values[part.type] = part.value;
  }
  const year = Number(values.year);
  const month = Number(values.month);
  const day = Number(values.day);
  const hour = Number(values.hour);
  const minute = Number(values.minute);
  const weekday = new Date(Date.UTC(year, month - 1, day, 12)).getUTCDay();
  return {
    year,
    month,
    day,
    hour,
    minute,
    weekday,
    weekdayName: WEEKDAYS[weekday],
    weekdayNarrow: WEEKDAYS_NARROW[weekday],
    key: `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`,
    time: `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`,
  };
}

function addDaysToKey(key, amount) {
  const [year, month, day] = key.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day, 12));
  date.setUTCDate(date.getUTCDate() + amount);
  return [
    date.getUTCFullYear(),
    String(date.getUTCMonth() + 1).padStart(2, "0"),
    String(date.getUTCDate()).padStart(2, "0"),
  ].join("-");
}

function diffDaysBetweenKeys(fromKey, toKey) {
  const from = Date.parse(`${fromKey}T00:00:00Z`);
  const to = Date.parse(`${toKey}T00:00:00Z`);
  return Math.round((to - from) / DAY_MS);
}

function todayKey() {
  return beijingInfo(new Date()).key;
}

function timeRangeText(event) {
  if (!event.exam_start || !event.exam_time_known) return "";
  const start = beijingInfo(event.exam_start);
  if (!start) return "";
  const end = event.exam_end ? beijingInfo(event.exam_end) : null;
  if (!end) return start.time;
  if (end.key === start.key) return `${start.time}–${end.time}`;
  return `${start.time}–${end.month}月${end.day}日 ${end.time}`;
}

function scheduleText(event, options = {}) {
  const { includeWeekday = true } = options;
  if (!event.exam_start) return "时间待确认";
  const start = beijingInfo(event.exam_start);
  if (!start) return "时间待确认";
  let text = `${start.month}月${start.day}日`;
  if (includeWeekday) text += ` ${start.weekdayName}`;
  if (!event.exam_time_known) {
    text += " · 时间待确认";
    return text;
  }
  text += ` · ${timeRangeText(event)}`;
  return text;
}

function deadlineText(event, options = {}) {
  if (!event.deadline) return "";
  const info = beijingInfo(event.deadline);
  if (!info) return "";
  let text = `${info.month}月${info.day}日`;
  if (options.includeWeekday) text += ` ${info.weekdayName}`;
  if (event.deadline_time_known) text += ` ${info.time}`;
  return text;
}

function compactScheduleText(event) {
  if (!event.exam_start) return "-";
  const start = beijingInfo(event.exam_start);
  if (!start) return "-";
  const startDate = `${start.month}/${start.day}`;
  if (!event.exam_time_known) return `${startDate} · -`;
  const end = event.exam_end ? beijingInfo(event.exam_end) : null;
  if (!end) return `${startDate} · ${start.time}`;
  if (end.key === start.key) return `${startDate} · ${start.time}–${end.time}`;
  if (end.time === start.time) return `${startDate}–${end.month}/${end.day} · ${start.time}`;
  return `${startDate} ${start.time}–${end.month}/${end.day} ${end.time}`;
}

function compactDeadlineText(event) {
  if (!event.deadline) return "";
  const info = beijingInfo(event.deadline);
  if (!info) return "";
  return `${info.month}/${info.day}${event.deadline_time_known ? ` ${info.time}` : ""}`;
}

function deadlineHint(event) {
  if (!event.deadline) return "未注明";
  const info = beijingInfo(event.deadline);
  if (!info) return "未注明";
  const days = diffDaysBetweenKeys(todayKey(), info.key);
  if (days < 0) return "已过截止";
  if (days === 0) return "今天截止";
  if (days === 1) return "明天截止";
  return `${days} 天后截止`;
}

function relativeDayLabel(event) {
  if (!event.exam_start) return "待确认";
  const info = beijingInfo(event.exam_start);
  if (!info) return "待确认";
  const days = diffDaysBetweenKeys(todayKey(), info.key);
  if (days < 0) return "已结束";
  if (days === 0) return "今天";
  if (days === 1) return "明天";
  if (days === 2) return "后天";
  return `${days} 天后`;
}

function relativeTimestamp(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const diff = Date.now() - date.getTime();
  if (diff < 0) return "刚刚";
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "昨天";
  if (days < 7) return `${days} 天前`;
  const info = beijingInfo(date);
  return info ? `${info.month}月${info.day}日` : "";
}

function parsedDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function getPhase(event, now = new Date()) {
  if (!event || event.ignored) return "ignored";
  if (event.status === "done") return "done";
  if (event.status === "cancelled") return "cancelled";
  if (!event.exam_start) return "review";
  const start = parsedDate(event.exam_start);
  if (!start) return "review";
  if (!event.exam_time_known) {
    const dayEnd = new Date(start.getTime() + DAY_MS);
    return now >= dayEnd ? "ended" : "review";
  }
  const explicitEnd = parsedDate(event.exam_end);
  const deadline = parsedDate(event.deadline);
  let end = explicitEnd;
  // A far-future deadline marks an open assessment window rather than a fixed slot.
  if (!end && deadline && deadline.getTime() - start.getTime() > 12 * 3_600_000) {
    end = deadline;
  }
  end = end
    || (event.duration_minutes
      ? new Date(start.getTime() + Number(event.duration_minutes) * 60_000)
      : new Date(start.getTime() + 2 * 3_600_000));
  if (now >= end) return "ended";
  if (now >= start) return "live";
  return "upcoming";
}

function isReviewEvent(event) {
  if (!event || event.status !== "pending" || event.ignored) return false;
  const phase = getPhase(event);
  if (phase === "ended") return false;
  return Boolean(event.needs_review || !event.exam_start || !event.exam_time_known);
}

function isActiveEvent(event) {
  if (!event) return false;
  const phase = getPhase(event);
  return !event.ignored
    && event.status === "pending"
    && phase !== "ended"
    && phase !== "done"
    && phase !== "cancelled"
    && phase !== "ignored";
}

function isEndedPending(event) {
  return Boolean(event)
    && !event.ignored
    && event.status === "pending"
    && getPhase(event) === "ended";
}

function sortByExamStart(a, b) {
  const aTime = parsedDate(a.exam_start)?.getTime() ?? Number.MAX_SAFE_INTEGER;
  const bTime = parsedDate(b.exam_start)?.getTime() ?? Number.MAX_SAFE_INTEGER;
  if (aTime !== bTime) return aTime - bTime;
  return String(a.company || "").localeCompare(String(b.company || ""), "zh-CN");
}

function activeEvents() {
  return state.events.filter(isActiveEvent).sort(sortByExamStart);
}

function reviewEvents() {
  return activeEvents().filter(isReviewEvent);
}

function statusInfo(event) {
  const phase = getPhase(event);
  if (event.ignored) return { label: "已忽略", className: "is-ignored" };
  if (phase === "done") return { label: "已完成", className: "is-done" };
  if (phase === "cancelled") return { label: "已取消", className: "is-cancelled" };
  if (isReviewEvent(event)) return { label: "待确认", className: "is-review" };
  if (phase === "live") return { label: "进行中", className: "is-live" };
  if (phase === "ended") return { label: "已结束", className: "is-ended" };
  return { label: relativeDayLabel(event), className: "is-upcoming" };
}

function phaseClass(event) {
  const phase = getPhase(event);
  if (phase === "review") return isReviewEvent(event) ? "is-review" : "is-upcoming";
  return `is-${phase}`;
}

function displayCompany(event) {
  return event.company || "公司待确认";
}

function displayRole(event) {
  return event.role || "岗位未注明";
}

function eventKind(event) {
  return event?.kind === "interview" ? "interview" : "exam";
}

function isInterviewEvent(event) {
  return eventKind(event) === "interview";
}

function kindLabel(event) {
  return KIND_LABELS[eventKind(event)];
}

function kindBadge(event) {
  const kind = eventKind(event);
  return `<span class="kind-chip is-${kind}">${KIND_LABELS[kind]}</span>`;
}

function eventNoun(event) {
  return isInterviewEvent(event) ? "面试" : "笔试";
}

function eventLinkLabel(event) {
  return isInterviewEvent(event) ? "面试入口" : "考试入口";
}

function modeLabel(mode) {
  if (mode === "online") return "线上";
  if (mode === "offline") return "线下";
  return "";
}

function reviewReason(event) {
  const missing = [];
  if (!event.company) missing.push("公司名称");
  if (!event.exam_start) missing.push(`${eventNoun(event)}时间`);
  else if (!event.exam_time_known) missing.push("具体开始时间");
  if (!missing.length) return "有信息待你确认";
  return `${missing.join("、")}待确认`;
}

function deadlineIsUrgent(event) {
  if (!event.deadline) return false;
  const deadline = parsedDate(event.deadline);
  if (!deadline) return false;
  return deadline.getTime() - Date.now() <= 48 * 3_600_000;
}

function focusCountdown(event) {
  const phase = getPhase(event);
  if (phase === "live") return { primary: "进行中", unit: "现在", text: true };
  if (!event.exam_time_known || !event.exam_start) {
    return { primary: "待定", unit: "时间待确认", text: true };
  }
  const start = parsedDate(event.exam_start);
  if (!start) return { primary: "待定", unit: "时间待确认", text: true };
  const diff = start.getTime() - Date.now();
  if (diff <= 0) return { primary: "今天", unit: "即将开始", text: true };
  if (diff < 3_600_000) {
    return { primary: String(Math.max(1, Math.ceil(diff / 60_000))), unit: "分钟后", text: false };
  }
  if (diff < DAY_MS) {
    return { primary: String(Math.ceil(diff / 3_600_000)), unit: "小时后", text: false };
  }
  const days = Math.max(1, diffDaysBetweenKeys(todayKey(), beijingInfo(start).key));
  return { primary: String(days), unit: "天后", text: false };
}

function syncCountsSummary(account) {
  const counts = account.last_sync_counts || {};
  const scanned = Number(counts.scanned || 0);
  const created = Number(counts.created || 0);
  const merged = Number(counts.merged || 0);
  const reclassified = Number(counts.reclassified || 0);
  const llmCalled = Number(counts.llm_called || 0);
  const llmMatched = Number(counts.llm_matched || 0);
  const llmErrors = Number(counts.llm_errors || 0);
  if (!scanned && !created && !merged && !reclassified && !llmCalled) {
    return "没有发现新的笔试或面试邮件";
  }
  const parts = [`检查 ${scanned} 封`];
  if (created) parts.push(createdBreakdown(counts) || `新增 ${created} 场`);
  if (reclassified) parts.push(`重新识别 ${reclassified} 条`);
  if (merged) parts.push(`合并 ${merged} 条提醒`);
  if (llmCalled) parts.push(`AI 识别 ${llmMatched}/${llmCalled} 条`);
  if (llmErrors) parts.push(`AI 调用失败 ${llmErrors} 次`);
  if (counts.errors) parts.push(`${counts.errors} 封读取失败`);
  return parts.join(" · ");
}

function createdBreakdown(counts) {
  const exams = Number(counts.created_exams || 0);
  const interviews = Number(counts.created_interviews || 0);
  if (!exams && !interviews) return "";
  return `新增 ${exams + interviews} 场（笔试 ${exams} / 面试 ${interviews}）`;
}

function accountStatusInfo(account) {
  if (account.last_sync_status === "syncing") {
    return { className: "is-syncing", text: `正在读取最近 ${account.sync_days} 天邮件…`, detail: "" };
  }
  if (account.last_sync_status === "error") {
    return {
      className: "is-error",
      text: "上次同步失败",
      detail: account.last_sync_at ? `尝试于 ${relativeTimestamp(account.last_sync_at)}` : "请检查邮箱设置",
    };
  }
  if (account.last_sync_status === "ok") {
    return {
      className: "is-ok",
      text: `上次同步 · ${relativeTimestamp(account.last_sync_at) || "刚刚"}`,
      detail: syncCountsSummary(account),
    };
  }
  return { className: "is-idle", text: "等待首次同步", detail: "首次同步会读取最近的邮件" };
}

// ---------------------------------------------------------------------------
// API and data
// ---------------------------------------------------------------------------

class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function api(path, options = {}) {
  const request = { method: options.method || "GET", headers: {} };
  if (request.method !== "GET") {
    request.headers["X-Campus-Radar-Request"] = "1";
  }
  if (options.body !== undefined) {
    request.headers["Content-Type"] = "application/json";
    request.body = JSON.stringify(options.body);
  }
  let response;
  try {
    response = await fetch(path, request);
  } catch {
    throw new ApiError("无法连接本地服务，请确认校招雷达正在运行。", 0);
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const message = typeof data?.detail === "string"
      ? data.detail
      : `请求失败（${response.status}）`;
    throw new ApiError(message, response.status);
  }
  return data;
}

async function loadAllData() {
  const [events, accounts, providers, meta, aiSettings] = await Promise.all([
    api("/api/events"),
    api("/api/accounts"),
    api("/api/providers"),
    api("/api/meta"),
    api("/api/ai-settings"),
  ]);
  state.events = Array.isArray(events) ? events : [];
  state.accounts = Array.isArray(accounts) ? accounts : [];
  state.providers = Array.isArray(providers) ? providers : [];
  state.meta = meta || state.meta;
  state.aiSettings = aiSettings || state.aiSettings;
}

async function refreshData({ render = true } = {}) {
  const [events, accounts, meta, aiSettings] = await Promise.all([
    api("/api/events"),
    api("/api/accounts"),
    api("/api/meta"),
    api("/api/ai-settings"),
  ]);
  state.events = events;
  state.accounts = accounts;
  state.meta = meta;
  state.aiSettings = aiSettings || state.aiSettings;
  updateSidebar();
  if (render) renderCurrentView();
}

async function refreshAccountsOnly() {
  state.accounts = await api("/api/accounts");
  updateSidebar();
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

async function boot() {
  el.boot.classList.remove("is-hidden");
  const priorError = el.boot.querySelector(".boot-error, .boot-actions");
  if (priorError) priorError.remove();
  el.boot.querySelector(".boot-title").textContent = "正在校准雷达";
  el.boot.querySelector(".boot-copy").textContent = "整理你的校招日程…";

  try {
    await loadAllData();
    updateSidebar();
    renderCurrentView({ scroll: false, animate: true });
    state.booted = true;
    window.setTimeout(() => el.boot.classList.add("is-hidden"), 250);
    if (state.accounts.some((account) => account.last_sync_status === "syncing")) {
      state.syncNotice = false;
      startSyncPolling();
    }
  } catch (error) {
    showBootError(error);
  }
}

function showBootError(error) {
  el.boot.querySelector(".boot-title").textContent = "暂时连不上本地服务";
  el.boot.querySelector(".boot-copy").textContent = "确认服务启动后，可以再试一次。";
  const box = document.createElement("div");
  box.className = "boot-error";
  box.textContent = error?.message || "未知错误";
  const actions = document.createElement("div");
  actions.className = "boot-actions";
  actions.innerHTML = `<button class="button button-primary button-small" type="button" data-action="retry-boot">重新加载</button>`;
  el.boot.append(box, actions);
}

// ---------------------------------------------------------------------------
// Navigation + layout
// ---------------------------------------------------------------------------

function navigate(view, { scroll = true } = {}) {
  if (!VALID_VIEWS.has(view)) view = "dashboard";
  if (window.location.hash !== `#${view}`) {
    window.location.hash = view;
    return;
  }
  state.view = view;
  if (state.drawer) closeDrawer();
  closeSidebar();
  renderCurrentView({ scroll, animate: true });
}

function handleHashChange() {
  const nextView = viewFromLocation();
  if (nextView === state.view) return;
  state.view = nextView;
  if (state.drawer) closeDrawer();
  closeSidebar();
  renderCurrentView({ scroll: true, animate: true });
}

let entryAnimationTimer = 0;

function renderCurrentView({ scroll = false, animate = true } = {}) {
  document.title = `${VIEW_TITLES[state.view]} · 校招雷达`;
  updateSidebar();
  if (entryAnimationTimer) {
    window.clearTimeout(entryAnimationTimer);
    entryAnimationTimer = 0;
  }
  el.root.classList.toggle("is-entering", animate);
  if (state.view === "dashboard") {
    el.root.innerHTML = renderDashboard();
  } else if (state.view === "library") {
    el.root.innerHTML = renderLibrary();
  } else if (state.view === "models") {
    el.root.innerHTML = renderModels();
  } else {
    state.providerId = "";
    el.root.innerHTML = renderAccounts();
    updateProviderUI("", { initial: true });
  }
  if (animate) {
    entryAnimationTimer = window.setTimeout(() => {
      el.root.classList.remove("is-entering");
      entryAnimationTimer = 0;
    }, 1000);
  }
  if (scroll) window.scrollTo({ top: 0, behavior: "smooth" });
}

function updateSidebar() {
  document.querySelectorAll("[data-nav]").forEach((button) => {
    const active = button.dataset.nav === state.view;
    button.classList.toggle("is-active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
}

function renderDemoBanner() {
  if (!state.meta?.demo_count) return "";
  return `<div class="demo-banner">
    <span class="demo-tag">DEMO</span>
    <p>你正在查看示例数据，它们不会连接真实邮箱。</p>
    <button class="text-button" type="button" data-action="clear-demo">清除示例</button>
  </div>`;
}

function viewHeader({ eyebrow, title, subtitle, actions = "", withDemo = true }) {
  return `<header class="view-header">
    <div>
      <div class="eyebrow">${escapeHtml(eyebrow)}</div>
      <h1 class="view-heading">${title}</h1>
      <p class="view-subtitle">${escapeHtml(subtitle)}</p>
    </div>
    ${actions ? `<div class="header-actions">${actions}</div>` : ""}
  </header>
  ${withDemo ? renderDemoBanner() : ""}`;
}

function headerActions({ refresh = true, add = false } = {}) {
  return [
    refresh ? `<button class="button button-ghost" type="button" data-action="refresh">刷新</button>` : "",
    add ? `<button class="button button-primary" type="button" data-action="add-event">手动添加</button>` : "",
  ].join("");
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

function renderDashboard() {
  const nowInfo = beijingInfo(new Date());
  const active = activeEvents();
  const ready = active.filter((event) => !isReviewEvent(event));
  const review = active.filter(isReviewEvent);
  const focus = ready[0] || review[0] || active[0] || null;
  const events = state.events;
  const doneCount = events.filter((event) => !event.ignored && event.status === "done").length;
  const next7 = active.filter((event) => {
    if (!event.exam_start) return false;
    const dateKey = beijingInfo(event.exam_start)?.key;
    if (!dateKey) return false;
    const gap = diffDaysBetweenKeys(todayKey(), dateKey);
    return gap >= 0 && gap <= 6;
  }).length;
  const noEvents = events.length === 0;

  return `<div class="dashboard">
    <header class="view-header dashboard-header">
      <div>
        <div class="eyebrow">TODAY · ${WEEKDAYS_EN[nowInfo.weekday]}, ${MONTHS_EN[nowInfo.month - 1]} ${nowInfo.day}</div>
        <h1 class="view-heading">接下来，稳稳拿下。</h1>
      </div>
      <div class="header-actions">${headerActions({ refresh: true, add: true })}</div>
    </header>
    ${renderDemoBanner()}
    ${renderSummary({ active, review, doneCount, next7 })}
    ${renderFocusCard(focus, noEvents)}
    ${noEvents ? renderOnboarding() : (active.length ? renderEventPanel(active, focus) : "")}
  </div>`;
}

function renderFocusCard(event, noEvents) {
  if (!event) {
    const title = noEvents ? "下一场安排，还在邮箱里。" : "这一轮，先告一段落。";
    const copy = noEvents
      ? "连接招聘邮箱后，雷达会自动识别笔试和面试邀请、时间、截止确认和入口链接。"
      : "目前没有待参加的笔试或面试。已完成或已结束的记录，都收在日程里。";
    const actions = noEvents
      ? `<div class="focus-actions">
          <button class="button button-primary" type="button" data-action="focus-account-form">连接招聘邮箱</button>
          <button class="button button-ghost" type="button" data-action="load-demo">看看示例</button>
        </div>`
      : `<div class="focus-actions">
          <button class="button button-primary" type="button" data-nav="library">打开日程</button>
          <button class="button button-ghost" type="button" data-action="add-event">手动添加</button>
        </div>`;
    return `<article class="focus-card">
      <div class="focus-empty">
        <div class="focus-kicker">CAMPUS-RADAR · 待命</div>
        <h2>${title}</h2>
        <p>${copy}</p>
        ${actions}
      </div>
    </article>`;
  }

  const countdown = focusCountdown(event);
  const url = safeHttpUrl(event.exam_url);
  const secondMetaLabel = event.deadline
    ? (isInterviewEvent(event) ? "确认截止" : "截止时间")
    : (event.duration_minutes
      ? (isInterviewEvent(event) ? "面试时长" : "作答时长")
      : (isInterviewEvent(event) ? "面试形式" : "考试形式"));
  const secondMetaValue = event.deadline
    ? deadlineText(event, { includeWeekday: false })
    : (event.duration_minutes ? `${event.duration_minutes} 分钟` : (modeLabel(event.mode) || "待确认"));

  return `<article class="focus-card">
    <div class="focus-kicker">
      ${isReviewEvent(event) ? "NEEDS REVIEW · 待确认" : "NEXT UP · 下一场"}
      <span class="focus-kind is-${eventKind(event)}">${kindLabel(event)}</span>
    </div>
    <div class="focus-main">
      <div>
        <div class="focus-company">${escapeHtml(displayCompany(event))}</div>
        <div class="focus-role">${escapeHtml(displayRole(event))}${event.interview_round ? ` · ${escapeHtml(event.interview_round)}` : ""}</div>
      </div>
      <div class="focus-countdown${countdown.text ? " is-text" : ""}">
        <strong>${escapeHtml(countdown.primary)}</strong>
        <span>${escapeHtml(countdown.unit)}</span>
      </div>
    </div>
    <div class="focus-meta">
      <div class="focus-meta-item">
        <span>${eventNoun(event)}时间</span>
        <strong>${escapeHtml(scheduleText(event))}</strong>
      </div>
      <div class="focus-meta-item">
        <span>${escapeHtml(secondMetaLabel)}</span>
        <strong>${escapeHtml(secondMetaValue)}</strong>
      </div>
    </div>
    <div class="focus-actions">
      <button class="button button-primary" type="button" data-action="open-event" data-id="${event.id}">查看详情</button>
      ${url ? `<a class="button button-ghost" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${eventLinkLabel(event)}</a>` : ""}
    </div>
  </article>`;
}

function renderSummary({ active, review, doneCount, next7 }) {
  const items = [
    { value: active.length, label: "待参加" },
    { value: next7, label: "未来 7 天" },
    { value: review.length, label: "待确认", className: review.length ? "is-warn" : "" },
    { value: doneCount, label: "已完成" },
  ];
  return `<section class="summary-strip" aria-label="日程概览">
    ${items.map((item) => `<div class="summary-item ${item.className || ""}">
      <strong>${item.value}</strong>
      <span>${escapeHtml(item.label)}</span>
    </div>`).join("")}
  </section>`;
}

function renderEventPanel(active, focus) {
  const rest = focus ? active.filter((event) => event.id !== focus.id) : active;
  const limited = rest.slice(0, 6);
  return `<section class="panel events-panel">
    <div class="panel-header with-border">
      <div>
        <h2 class="panel-title">接下来的安排</h2>
        <p class="panel-subtitle">共 ${active.length} 场${rest.length > limited.length ? `，这里展示最近 ${limited.length} 场` : ""}</p>
      </div>
      <button class="text-button" type="button" data-nav="library">全部 ${active.length} 场</button>
    </div>
    <div class="event-list">
      ${limited.length ? limited.map(renderEventCard).join("") : `<div class="events-empty">暂时没有更多待参加的笔试或面试。</div>`}
    </div>
  </section>`;
}

function eventDateBlock(event) {
  if (!event.exam_start) {
    return `<div class="event-date is-unknown">
      <span class="event-date-month">日期</span>
      <span class="event-date-day is-text">待定</span>
      <span class="event-date-week">TIME</span>
    </div>`;
  }
  const info = beijingInfo(event.exam_start);
  if (!info) return "";
  const unknown = !event.exam_time_known;
  return `<div class="event-date${unknown ? " is-unknown" : ""}">
    <span class="event-date-month">${info.month}月</span>
    <span class="event-date-day">${info.day}</span>
    <span class="event-date-week">${unknown ? "待定" : info.weekdayNarrow}</span>
  </div>`;
}

function renderEventCard(event) {
  const status = statusInfo(event);
  const phase = phaseClass(event);
  const platform = event.platform || modeLabel(event.mode);
  const deadline = event.deadline ? deadlineText(event, { includeWeekday: false }) : "";
  const meta = [];
  meta.push(`<span class="meta-item"><span>${escapeHtml(scheduleText(event, { includeWeekday: false }))}</span></span>`);
  if (platform) {
    meta.push(`<span class="meta-item"><span>${escapeHtml(platform)}</span></span>`);
  }
  if (deadline && event.status === "pending" && !event.ignored) {
    meta.push(`<span class="meta-item is-deadline${deadlineIsUrgent(event) ? " is-overdue" : ""}"><span>截止 ${escapeHtml(deadline)}</span></span>`);
  }
  return `<article class="event-card ${phase}" data-event-id="${event.id}">
    <button class="event-card-main" type="button" data-action="open-event" data-id="${event.id}" aria-label="查看 ${escapeHtml(displayCompany(event))} ${escapeHtml(displayRole(event))} ${eventNoun(event)}详情">
      ${eventDateBlock(event)}
      <div class="event-content">
        <div class="company-line">
          <span class="company-name">${escapeHtml(displayCompany(event))}</span>
          ${kindBadge(event)}
        </div>
        <div class="role-name">${escapeHtml(displayRole(event))}${event.interview_round ? ` · ${escapeHtml(event.interview_round)}` : ""}</div>
        <div class="event-meta">${meta.join("")}</div>
      </div>
    </button>
    <div class="event-side">
      <span class="status-chip ${status.className}">${escapeHtml(status.label)}</span>
    </div>
  </article>`;
}

function renderOnboarding() {
  return `<section class="panel onboarding-panel">
    <div class="onboarding-intro">
      <div class="eyebrow">HOW IT WORKS</div>
      <h2>让雷达替你盯着收件箱。</h2>
      <p>笔试和面试邀请常常埋在提醒、测评通知和转发邮件里。这里把它们统一抽出来，只需要你确认少量缺失信息。</p>
    </div>
    <ol class="onboarding-steps">
      <li class="onboarding-step">
        <span class="step-index">01</span>
        <div><h3>连接邮箱</h3><p>支持 QQ、163、126、Gmail 以及学校或企业的 IMAP 邮箱。</p></div>
      </li>
      <li class="onboarding-step">
        <span class="step-index">02</span>
        <div><h3>自动抽取</h3><p>识别公司、岗位、笔试或面试时间、截止确认、平台和入口。</p></div>
      </li>
      <li class="onboarding-step">
        <span class="step-index">03</span>
        <div><h3>确认与跟踪</h3><p>处理提醒邮件去重，手动修正信息，按时间线逐场完成。</p></div>
      </li>
    </ol>
  </section>`;
}

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------

function kindScopedEvents() {
  return state.events.filter(
    (event) => state.kindFilter === "all" || eventKind(event) === state.kindFilter,
  );
}

function kindFilterCounts() {
  return {
    all: state.events.length,
    exam: state.events.filter((event) => eventKind(event) === "exam").length,
    interview: state.events.filter((event) => eventKind(event) === "interview").length,
  };
}

function filterCounts(events = kindScopedEvents()) {
  const active = events.filter(isActiveEvent);
  return {
    all: events.length,
    upcoming: active.filter((event) => !isReviewEvent(event)).length,
    review: active.filter(isReviewEvent).length,
    ended: events.filter(isEndedPending).length,
    done: events.filter((event) => !event.ignored && event.status === "done").length,
    ignored: events.filter((event) => event.ignored || event.status === "cancelled").length,
  };
}

function renderLibrary() {
  const kindCounts = kindFilterCounts();
  const counts = filterCounts();
  return `<div class="library-view">
    ${viewHeader({
      eyebrow: "LIBRARY · EXAMS & INTERVIEWS",
      title: "笔试与面试，一处查看。",
      subtitle: `${kindCounts.exam} 场笔试 · ${kindCounts.interview} 场面试，可按类型和状态筛选。`,
      actions: headerActions({ refresh: true, add: true }),
      withDemo: false,
    })}
    ${renderDemoBanner()}
    <div class="library-toolbar">
      <div class="filter-tabs" role="tablist" aria-label="筛选状态">
        ${LIBRARY_FILTERS.map((filter) => `<button class="filter-tab${state.libraryFilter === filter.id ? " is-active" : ""}" type="button" role="tab" aria-selected="${state.libraryFilter === filter.id}" data-filter="${filter.id}">
          ${filter.label}<span class="filter-count">${counts[filter.id] || 0}</span>
        </button>`).join("")}
      </div>
      <div class="library-tools">
        <div class="kind-switch" role="tablist" aria-label="筛选类型">
          ${KIND_FILTERS.map((kind) => `<button class="kind-switch-button${state.kindFilter === kind.id ? " is-active" : ""}" type="button" role="tab" aria-selected="${state.kindFilter === kind.id}" data-kind-filter="${kind.id}">
            ${kind.label}<span class="filter-count">${kindCounts[kind.id] || 0}</span>
          </button>`).join("")}
        </div>
        <label class="search-field">
          ${icon("search", 15)}
          <input class="search-input" id="library-search" type="search" placeholder="搜索公司、岗位或平台" autocomplete="off" value="${escapeHtml(state.libraryQuery)}" aria-label="搜索日程">
        </label>
      </div>
    </div>
    <div id="library-results">${renderLibraryResults()}</div>
  </div>`;
}

function updateLibraryKindUI() {
  document.querySelectorAll("[data-kind-filter]").forEach((node) => {
    const active = node.dataset.kindFilter === state.kindFilter;
    node.classList.toggle("is-active", active);
    node.setAttribute("aria-selected", String(active));
  });
  const counts = filterCounts();
  document.querySelectorAll("[data-filter]").forEach((node) => {
    const count = node.querySelector(".filter-count");
    if (count) count.textContent = String(counts[node.dataset.filter] || 0);
  });
  const results = document.getElementById("library-results");
  if (results) results.innerHTML = renderLibraryResults();
}

function matchesSearch(event, query) {
  if (!query) return true;
  const haystack = [
    event.company,
    event.role,
    event.interview_round,
    event.platform,
    event.source_subject,
    event.notes,
    event.location,
  ].filter(Boolean).join(" ").toLocaleLowerCase("zh-CN");
  return haystack.includes(query.toLocaleLowerCase("zh-CN"));
}

function sortNewestFirst(a, b) {
  const aTime = parsedDate(a.exam_start)?.getTime() || parsedDate(a.updated_at)?.getTime() || 0;
  const bTime = parsedDate(b.exam_start)?.getTime() || parsedDate(b.updated_at)?.getTime() || 0;
  return bTime - aTime;
}

function renderLibraryResults() {
  let events = kindScopedEvents().filter((event) => matchesSearch(event, state.libraryQuery.trim()));
  const groups = [];

  if (state.libraryFilter === "all") {
    const active = events.filter(isActiveEvent).sort(sortByExamStart);
    groups.push(
      { title: "待参加", events: active.filter((event) => !isReviewEvent(event)) },
      { title: "待确认", events: active.filter(isReviewEvent) },
      { title: "已结束", events: events.filter(isEndedPending).sort(sortByExamStart) },
      { title: "已完成", events: events.filter((event) => !event.ignored && event.status === "done").sort(sortNewestFirst) },
      { title: "已忽略", events: events.filter((event) => event.ignored || event.status === "cancelled").sort(sortNewestFirst) },
    );
  } else if (state.libraryFilter === "upcoming") {
    groups.push({
      title: "待参加",
      events: events.filter((event) => isActiveEvent(event) && !isReviewEvent(event)).sort(sortByExamStart),
    });
  } else if (state.libraryFilter === "review") {
    groups.push({
      title: "待确认",
      events: events.filter(isReviewEvent).sort(sortByExamStart),
    });
  } else if (state.libraryFilter === "ended") {
    groups.push({
      title: "已结束",
      events: events.filter(isEndedPending).sort(sortByExamStart),
    });
  } else if (state.libraryFilter === "done") {
    groups.push({
      title: "已完成",
      events: events.filter((event) => !event.ignored && event.status === "done").sort(sortNewestFirst),
    });
  } else if (state.libraryFilter === "ignored") {
    groups.push({
      title: "已忽略",
      events: events.filter((event) => event.ignored || event.status === "cancelled").sort(sortNewestFirst),
    });
  }

  const nonEmpty = groups.filter((group) => group.events.length > 0);
  if (!nonEmpty.length) {
    const isSearch = Boolean(state.libraryQuery.trim());
    const scope = state.kindFilter === "interview"
      ? "面试"
      : (state.kindFilter === "exam" ? "笔试" : "笔试或面试");
    return `<div class="library-empty">
      ${renderEmptyState({
        iconName: isSearch ? "search" : "inbox",
        title: isSearch ? "没有找到匹配的日程" : "这个分类还没有记录",
        copy: isSearch ? "换个公司名或岗位关键词试试，搜索会同时匹配邮件主题。" : `连接邮箱同步后，识别出的${scope}会收进这里。`,
        actions: isSearch
          ? `<button class="button button-ghost button-small" type="button" data-action="clear-search">清除搜索</button>`
          : `<button class="button button-primary button-small" type="button" data-action="focus-account-form">连接邮箱</button>`,
      })}
    </div>`;
  }

  return nonEmpty.map((group) => `
    <section class="library-group">
      <div class="library-group-head">
        <h2 class="library-group-title">${escapeHtml(group.title)}</h2>
        <span class="library-group-count">${String(group.events.length).padStart(2, "0")}</span>
      </div>
      <div class="library-table">
        <div class="library-table-head" aria-hidden="true">
          <span>公司</span><span>岗位</span><span>类型</span><span>时间</span><span>截止</span><span>状态</span>
        </div>
        ${group.events.map(renderLibraryRow).join("")}
      </div>
    </section>
  `).join("");
}

function renderLibraryRow(event) {
  const status = statusInfo(event);
  const phase = phaseClass(event);
  const url = safeHttpUrl(event.exam_url);
  const dimmed = event.ignored || event.status === "done" || event.status === "cancelled" || getPhase(event) === "ended";
  const isDone = event.status === "done";
  const deadline = compactDeadlineText(event) || "-";
  const fullDeadlineText = event.deadline ? deadlineText(event, { includeWeekday: true }) : "";
  const deadlineHintText = event.deadline ? deadlineHint(event) : "";
  const deadlineTitle = event.deadline
    ? `${fullDeadlineText}${deadlineHintText && deadlineHintText !== "未注明" ? ` · ${deadlineHintText}` : ""}`
    : "未注明截止时间";
  const schedule = compactScheduleText(event);
  const fullSchedule = scheduleText(event);
  const companyName = event.company || "-";
  const roleText = [event.role, event.interview_round].filter(Boolean).join(" · ") || "-";
  return `<article class="library-row${dimmed ? " is-dimmed" : ""}" data-event-id="${event.id}">
    <button class="library-row-main" type="button" data-action="open-event" data-id="${event.id}" aria-label="查看 ${escapeHtml(displayCompany(event))} ${escapeHtml(displayRole(event))} ${eventNoun(event)}详情">
      <span class="library-company" title="${escapeHtml(companyName)}">${escapeHtml(companyName)}</span>
      <span class="library-role" title="${escapeHtml(roleText)}">${escapeHtml(roleText)}</span>
      <span class="library-type">${escapeHtml(kindLabel(event))}</span>
      <span class="library-cell library-time" title="${escapeHtml(fullSchedule)}">${escapeHtml(schedule)}</span>
      <span class="library-cell library-deadline" title="${escapeHtml(deadlineTitle)}">${escapeHtml(deadline)}</span>
      <span class="library-status">${escapeHtml(status.label)}</span>
    </button>
    <div class="library-row-actions">
      ${url ? `<a class="quick-action keep-mobile" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer" title="打开${eventLinkLabel(event)}" aria-label="打开${eventLinkLabel(event)}">${icon("external", 14)}</a>` : ""}
      <button class="quick-action keep-mobile${isDone ? " is-done" : ""}" type="button" data-action="toggle-done" data-id="${event.id}" title="${isDone ? "标记为待参加" : "标记为已完成"}" aria-label="${isDone ? "标记为待参加" : "标记为已完成"}">${icon("check", 14)}</button>
    </div>
  </article>`;
}

function renderEmptyState({ iconName = "inbox", title, copy, actions = "" }) {
  return `<div class="empty-state">
    <div class="empty-illustration">${icon(iconName, 27)}</div>
    <h2 class="empty-title">${escapeHtml(title)}</h2>
    <p class="empty-copy">${escapeHtml(copy)}</p>
    ${actions ? `<div class="empty-actions">${actions}</div>` : ""}
  </div>`;
}

// ---------------------------------------------------------------------------
// Accounts
// ---------------------------------------------------------------------------

function renderAccounts() {
  return `<div class="accounts-view">
    ${viewHeader({
      eyebrow: "CONNECT · MAILBOXES",
      title: "把招聘邮箱，接进来。",
      subtitle: "只读扫描最近邮件，不会发送、删除或修改邮件；授权码只加密保存在本机。",
      actions: headerActions({ refresh: true }),
      withDemo: false,
    })}
    ${renderDemoBanner()}
    <div class="accounts-layout${state.accounts.length ? "" : " is-empty"}">
      <div class="account-column">
        <div class="account-list">
          ${state.accounts.length ? state.accounts.map(renderAccountCard).join("") : `<div class="accounts-empty">还没有连接邮箱。连接后可以先手动同步，之后也可以开启自动检查。</div>`}
        </div>
        ${!state.accounts.length ? `<section class="mailbox-explainer">
          <div class="explainer-kicker">WHAT HAPPENS</div>
          <h3>同步时会发生什么</h3>
          <div class="explainer-list">
            <div class="explainer-row"><span class="explainer-num">01</span><p><strong>只读访问。</strong>不标记已读、不发送、不删除你的邮件。</p></div>
            <div class="explainer-row"><span class="explainer-num">02</span><p><strong>本地识别。</strong>只保留笔试或面试相关邮件正文，解析过程默认不经过任何云端模型。</p></div>
            <div class="explainer-row"><span class="explainer-num">03</span><p><strong>增量同步。</strong>按邮件 UID 检查新内容，提醒邮件会合并，手动修改过的字段不会被覆盖。</p></div>
          </div>
        </section>` : ""}
      </div>

      <div class="account-column add-account-column">
        <section class="panel add-account-panel" id="add-account-panel">
          <div class="panel-heading">
            <div class="eyebrow">ADD MAILBOX</div>
            <h2>连接一个邮箱</h2>
          </div>
          ${renderAccountForm()}
        </section>
      </div>
    </div>
  </div>`;
}

function renderModels() {
  return `<div class="models-view">
    ${viewHeader({
      eyebrow: "MODEL · AI RECOGNITION",
      title: "让识别，更懂招聘邮件。",
      subtitle: "可选接入 OpenAI 兼容模型；先判断邮件是否包含有效安排，再抽取字段。未配置或调用失败时回退本地规则。",
      actions: headerActions({ refresh: true }),
      withDemo: false,
    })}
    ${renderAISettingsPanel()}
  </div>`;
}

function renderAISettingsPanel() {
  const ai = state.aiSettings || {};
  const active = Boolean(ai.active);
  const hasKey = Boolean(ai.has_api_key);
  return `<section class="panel ai-settings-panel" id="ai-settings-panel">
    <div class="ai-settings-head">
      <div>
        <div class="eyebrow">RECOGNITION MODE</div>
        <h2>大模型识别</h2>
      </div>
      <span class="status-chip ${active ? "is-live" : "is-ignored"}">${active ? "已启用" : "未启用"}</span>
    </div>
    <form id="ai-settings-form">
      <div class="form-grid is-3">
        <div class="form-field is-full">
          <label class="field-label" for="ai-base-url">接口地址</label>
          <input class="input" id="ai-base-url" name="base_url" type="url" value="${escapeHtml(ai.base_url || "")}" placeholder="OpenAI 兼容的 API 地址，例如：https://api.deepseek.com/v1">
        </div>
        <div class="form-field">
          <label class="field-label" for="ai-model">模型名称</label>
          <input class="input" id="ai-model" name="model" type="text" value="${escapeHtml(ai.model || "")}" maxlength="200">
        </div>
        <div class="form-field">
          <label class="field-label" for="ai-max-calls">每次同步最多调用</label>
          <input class="input" id="ai-max-calls" name="max_calls_per_sync" type="number" min="1" max="300" value="${Number(ai.max_calls_per_sync || 20)}">
        </div>
        <div class="form-field">
          <label class="field-label" for="ai-api-key">API Key</label>
          <div class="password-wrap">
            <input class="input" id="ai-api-key" name="api_key" type="password" placeholder="${hasKey ? "已保存，留空不修改" : "sk-..."}" autocomplete="new-password">
            <button class="password-toggle" type="button" data-action="toggle-password" data-target="ai-api-key" aria-label="显示或隐藏 API Key">${icon("eye", 15)}</button>
          </div>
        </div>
      </div>
      <div class="form-error" data-form-error hidden></div>
      <div class="ai-settings-actions">
        <button class="button button-primary button-small" type="submit">保存设置</button>
        <button class="button button-ghost button-small" type="button" data-action="test-ai" title="先保存设置，再用已保存的配置测试连接">测试连接</button>
        ${hasKey ? `<button class="button button-ghost button-small is-danger" type="button" data-action="clear-ai-key">删除连接</button>` : ""}
      </div>
    </form>
  </section>`;
}

function renderAccountCard(account) {
  const status = accountStatusInfo(account);
  const isSyncing = account.last_sync_status === "syncing";
  const reauthOpen = state.reauthAccountId === account.id;
  const providerLabel = providerName(account.provider);
  const rawLabel = String(account.label || "").trim();
  const defaultLabel = `${providerLabel} · ${account.email || ""}`.trim();
  const label = !rawLabel || rawLabel === providerLabel || rawLabel.toLowerCase() === defaultLabel.toLowerCase()
    ? providerLabel
    : rawLabel;
  const showProviderTag = providerLabel && !label.toLowerCase().includes(providerLabel.toLowerCase());
  return `<article class="account-card${account.last_sync_status === "error" ? " is-error" : ""}" data-account-card="${account.id}">
    <div class="account-head">
      <div class="account-identity">
        <div class="account-label">${escapeHtml(label)}${showProviderTag ? `<span class="account-tag">${escapeHtml(providerLabel)}</span>` : ""}</div>
        <div class="account-email">${escapeHtml(account.email)}${account.folder && account.folder !== "INBOX" ? ` · ${escapeHtml(account.folder)}` : ""}</div>
      </div>
      <label class="account-auto-sync">
        <span class="switch">
          <input type="checkbox" data-autosync-account="${account.id}" ${account.auto_sync ? "checked" : ""}>
          <span class="switch-track"></span>
        </span>
        自动同步
      </label>
    </div>
    <div class="account-status ${status.className}">
      <span>${escapeHtml(status.text)}</span>
      ${status.detail ? `<span class="account-counts">${escapeHtml(status.detail)}</span>` : ""}
    </div>
    ${account.last_sync_status === "error" && account.last_sync_error ? `<div class="account-error">${escapeHtml(account.last_sync_error)}</div>` : ""}
    <div class="account-toolbar">
      <button class="button button-ghost button-small" type="button" data-action="sync-account" data-id="${account.id}" ${isSyncing ? "disabled" : ""}>${isSyncing ? "同步中…" : account.last_sync_status === "error" ? "重试同步" : "立即同步"}</button>
      <button class="button button-ghost button-small" type="button" data-action="rescan-account" data-id="${account.id}">重新识别</button>
      <button class="button button-ghost button-small" type="button" data-action="toggle-reauth" data-id="${account.id}">更新授权码</button>
      <button class="button button-ghost button-small is-danger" type="button" data-action="delete-account" data-id="${account.id}">移除邮箱</button>
    </div>
    ${reauthOpen ? renderReauthForm(account) : ""}
  </article>`;
}

function renderReauthForm(account) {
  return `<form class="account-reauth" data-reauth-form="${account.id}">
    <div class="account-reauth-title">更新 ${escapeHtml(providerName(account.provider))} 授权码</div>
    <div class="reauth-row">
      <div class="password-wrap">
        <input class="input" type="password" name="password" id="reauth-password-${account.id}" placeholder="输入新的授权码" autocomplete="new-password" required>
        <button class="password-toggle" type="button" data-action="toggle-password" data-target="reauth-password-${account.id}" aria-label="显示或隐藏授权码">${icon("eye", 15)}</button>
      </div>
      <button class="button button-primary button-small" type="submit">验证并保存</button>
      <button class="button button-ghost button-small" type="button" data-action="cancel-reauth">取消</button>
    </div>
    <div class="form-error" data-form-error hidden></div>
  </form>`;
}

function renderAccountForm() {
  const provider = providerById(state.providerId);
  const authLabel = provider?.auth_label || "授权码 / 密码";
  const passwordPlaceholder = provider
    ? (provider.custom ? "密码或授权码" : `粘贴 ${provider.auth_label}`)
    : "粘贴授权码或密码";

  return `<form id="account-form">
    <div class="form-grid">
      <div class="form-field is-full">
        <label class="field-label" for="account-email">邮箱地址<span class="required">*</span></label>
        <input class="input" id="account-email" name="email" type="email" placeholder="name@example.com" autocomplete="username" required>
      </div>
      ${state.providers.map((item) => `<div class="provider-hint" data-provider-hint="${escapeHtml(item.id)}" hidden><span class="provider-hint-name">${escapeHtml(item.name)}</span> · ${escapeHtml(item.hint)}</div>`).join("")}
    </div>

    <div class="form-grid">
      <div class="form-field is-full">
        <label class="field-label" for="account-password"><span data-auth-label>${escapeHtml(authLabel)}</span><span class="required">*</span></label>
        <div class="password-wrap">
          <input class="input" id="account-password" name="password" type="password" placeholder="${escapeHtml(passwordPlaceholder)}" autocomplete="new-password" required>
          <button class="password-toggle" type="button" data-action="toggle-password" data-target="account-password" aria-label="显示或隐藏授权码">${icon("eye", 15)}</button>
        </div>
      </div>
      <div class="form-field">
        <label class="field-label" for="account-label">备注名称</label>
        <input class="input" id="account-label" name="label" type="text" placeholder="例如：主投递邮箱" maxlength="80">
      </div>
      <div class="form-field">
        <label class="field-label" for="account-sync-days">首次同步范围</label>
        <select class="select" id="account-sync-days" name="sync_days">
          <option value="7">最近 7 天</option>
          <option value="14">最近 14 天</option>
          <option value="30" selected>最近 30 天</option>
          <option value="60">最近 60 天</option>
          <option value="90">最近 90 天</option>
        </select>
      </div>
    </div>

    <div class="custom-fields" data-custom-fields ${provider?.custom ? "" : "hidden"}>
      <div class="form-grid is-3">
        <div class="form-field" style="grid-column: span 1">
          <label class="field-label" for="custom-host">服务器地址<span class="required">*</span></label>
          <input class="input" id="custom-host" name="imap_host" type="text" placeholder="imap.example.com">
        </div>
        <div class="form-field">
          <label class="field-label" for="custom-port">端口</label>
          <input class="input" id="custom-port" name="imap_port" type="number" value="993" min="1" max="65535">
        </div>
        <div class="form-field">
          <label class="field-label" for="custom-folder">文件夹</label>
          <input class="input" id="custom-folder" name="folder" type="text" value="INBOX" placeholder="INBOX">
        </div>
      </div>
    </div>

    <div class="form-error" data-form-error hidden></div>
    <div class="form-actions">
      <button class="button button-primary" type="submit" data-submit-account>测试连接并添加</button>
    </div>
  </form>`;
}

function updateProviderUI(providerId, { initial = false } = {}) {
  const previousId = state.providerId;
  state.providerId = providerId;
  const provider = providerById(providerId);
  document.querySelectorAll("[data-provider-hint]").forEach((node) => {
    node.hidden = !provider || node.dataset.providerHint !== provider.id;
  });
  const customFields = document.querySelector("[data-custom-fields]");
  if (customFields) customFields.hidden = !provider?.custom;
  const authLabel = document.querySelector("[data-auth-label]");
  if (authLabel) authLabel.textContent = provider?.auth_label || "授权码 / 密码";
  const password = document.getElementById("account-password");
  if (!password) return;
  password.placeholder = provider
    ? (provider.custom ? "密码或授权码" : `粘贴 ${provider.auth_label}`)
    : "粘贴授权码或密码";
  if (!initial && provider && !provider.custom && previousId !== provider.id) password.value = "";
}

// ---------------------------------------------------------------------------
// Event drawer
// ---------------------------------------------------------------------------

function blankEvent() {
  return {
    id: null,
    account_id: null,
    kind: "exam",
    interview_round: "",
    company: "",
    role: "",
    exam_start: null,
    exam_end: null,
    exam_time_known: false,
    deadline: null,
    deadline_time_known: false,
    duration_minutes: null,
    platform: "",
    exam_url: "",
    mode: "unknown",
    location: "",
    access_code: "",
    status: "pending",
    ignored: false,
    needs_review: false,
    manually_edited: false,
    auto_notes: null,
    notes: "",
    source_subject: null,
    source_sender: null,
    source_received_at: null,
    source_body: null,
    source_count: 1,
    is_demo: false,
  };
}

function dateInputValue(value) {
  const info = beijingInfo(value);
  return info ? info.key : "";
}

function timeInputValue(value, timeKnown = true) {
  if (!timeKnown || !value) return "";
  const info = beijingInfo(value);
  return info ? info.time : "";
}

function formatMailTimestamp(value) {
  const info = beijingInfo(value);
  if (!info) return "";
  return `${info.month}月${info.day}日 ${String(info.hour).padStart(2, "0")}:${String(info.minute).padStart(2, "0")}`;
}

function showDrawerShell() {
  if (state.drawerCloseTimer) {
    window.clearTimeout(state.drawerCloseTimer);
    state.drawerCloseTimer = null;
  }
  if (el.drawer.hidden) {
    state.drawerLastFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  }
  el.drawer.hidden = false;
  el.drawerScrim.hidden = false;
  document.body.classList.add("drawer-open");
  window.requestAnimationFrame(() => {
    el.drawer.classList.add("is-open");
    el.drawerScrim.classList.add("is-visible");
  });
}

async function openEventDrawer(id = null, { create = false } = {}) {
  const token = (state.drawer?.token || 0) + 1;
  if (create) {
    state.drawer = {
      mode: "create",
      id: null,
      token,
      loading: false,
      saving: false,
      editing: true,
      error: null,
      event: blankEvent(),
    };
    showDrawerShell();
    renderDrawer();
    focusDrawer();
    return;
  }

  const cached = state.events.find((event) => event.id === Number(id)) || null;
  state.drawer = {
    mode: "edit",
    id: Number(id),
    token,
    loading: true,
    saving: false,
    editing: false,
    error: null,
    event: cached,
  };
  showDrawerShell();
  renderDrawer();
  focusDrawer();

  try {
    const event = await api(`/api/events/${Number(id)}`);
    if (!state.drawer || state.drawer.token !== token) return;
    state.drawer.event = event;
    state.drawer.loading = false;
    renderDrawer();
    focusDrawer();
  } catch (error) {
    if (!state.drawer || state.drawer.token !== token) return;
    state.drawer.loading = false;
    state.drawer.error = error.message || "读取记录失败";
    renderDrawer();
  }
}

function closeDrawer({ restoreFocus = true } = {}) {
  if (!state.drawer) return;
  const lastFocus = state.drawerLastFocus;
  state.drawer = null;
  el.drawer.classList.remove("is-open");
  el.drawerScrim.classList.remove("is-visible");
  document.body.classList.remove("drawer-open");
  if (state.drawerCloseTimer) window.clearTimeout(state.drawerCloseTimer);
  state.drawerCloseTimer = window.setTimeout(() => {
    if (!state.drawer) {
      el.drawer.hidden = true;
      el.drawerScrim.hidden = true;
      el.drawer.innerHTML = "";
    }
    state.drawerCloseTimer = null;
  }, 300);
  if (restoreFocus && lastFocus instanceof HTMLElement && document.contains(lastFocus)) {
    window.setTimeout(() => lastFocus.focus({ preventScroll: true }), 50);
  }
}

function focusDrawer() {
  el.drawer.querySelector("[data-action='close-drawer']")?.focus({ preventScroll: true });
}

function focusDrawerEditor() {
  el.drawer.querySelector("#event-company")?.focus({ preventScroll: true });
}

function drawerHeaderMarkup(event, mode, loading, error) {
  const kind = eventKind(event);
  const title = error
    ? "读取失败"
    : (mode === "create" ? `新的${KIND_LABELS[kind]}` : (event?.company || `${KIND_LABELS[kind]}详情`));
  const role = error
    ? "请关闭后重试"
    : (loading ? "正在读取邮件记录…" : (mode === "create" ? "手动补一条记录" : (event?.role || "岗位未注明")));
  const kicker = mode === "create"
    ? "MANUAL ENTRY · 手动添加"
    : (event?.is_demo
      ? "DEMO · 示例记录"
      : (kind === "interview" ? "INTERVIEW DETAIL · 面试详情" : "EXAM DETAIL · 笔试详情"));
  return `<div class="drawer-header">
    <div class="drawer-heading">
      <div class="drawer-kicker" data-kind-kicker>${kicker}</div>
      <div class="drawer-title-row">
        <h2 class="drawer-title" id="drawer-title" data-kind-title>${escapeHtml(title)}</h2>
      </div>
      <p class="drawer-role">${escapeHtml(role)}</p>
    </div>
    <button class="icon-button drawer-close" type="button" data-action="close-drawer" aria-label="关闭详情">${icon("x", 19)}</button>
  </div>`;
}

function renderEventDetail(event) {
  const kind = eventKind(event);
  const interview = kind === "interview";
  const status = statusInfo(event);
  const url = safeHttpUrl(event.exam_url);
  const needsReview = isReviewEvent(event);
  const autoNotes = String(event.auto_notes || "").split("\n").map((line) => line.trim()).filter(Boolean);
  const userNotes = String(event.notes || "").trim();
  const sourceBody = event.source_body || "";
  const sourceMeta = [event.source_sender, event.source_received_at ? formatMailTimestamp(event.source_received_at) : ""].filter(Boolean).join(" · ");
  const sourceCount = Number(event.source_count || 1);
  const metaItems = [
    `<span class="status-chip ${status.className}">${escapeHtml(status.label)}</span>`,
    (event.auto_notes || "").includes("大模型") ? `<span class="drawer-meta-text is-ai">${icon("sparkle", 12)}AI 识别</span>` : "",
    event.is_demo ? `<span class="drawer-meta-text">示例数据</span>` : "",
  ].filter(Boolean).join("");
  const entryLink = url
    ? `<a class="drawer-entry-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${icon("external", 12)}打开${eventLinkLabel(event)}</a>`
    : "";
  const facts = [
    { label: `${eventNoun(event)}时间`, value: scheduleText(event) },
  ];
  if (event.deadline) {
    const hint = deadlineHint(event);
    facts.push({
      label: isInterviewEvent(event) ? "确认截止" : "截止时间",
      value: `${deadlineText(event, { includeWeekday: true })}${hint && hint !== "未注明" ? ` · ${hint}` : ""}`,
    });
  }
  if (event.duration_minutes) {
    facts.push({
      label: isInterviewEvent(event) ? "面试时长" : "作答时长",
      value: `${event.duration_minutes} 分钟`,
    });
  }
  const platform = [event.platform, modeLabel(event.mode)].filter(Boolean).join(" · ");
  if (platform) {
    facts.push({ label: isInterviewEvent(event) ? "面试平台" : "考试平台", value: platform });
  }
  if (event.location) {
    facts.push({ label: isInterviewEvent(event) ? "面试地点" : "考试地点", value: event.location, full: true });
  }
  if (event.access_code) {
    facts.push({
      label: isInterviewEvent(event) ? "会议号 / 密码" : "口令 / 邀请码",
      value: event.access_code,
      full: true,
    });
  }
  const footerLeft = `<div class="drawer-footer-left">
    <button class="text-button is-danger" type="button" data-action="delete-event" data-id="${event.id}">删除</button>
    <button class="text-button" type="button" data-action="toggle-ignore" data-id="${event.id}">${event.ignored ? "恢复显示" : "忽略这条"}</button>
  </div>`;

  el.drawer.innerHTML = `${drawerHeaderMarkup(event, "edit", false, null)}
    <div class="drawer-scroll">
      <div class="drawer-body drawer-detail">
        <div class="drawer-meta">
          <div class="drawer-meta-main">${metaItems}</div>
          ${entryLink}
        </div>
        ${needsReview ? `<div class="drawer-alert">${icon("alert", 14)}<span>${escapeHtml(reviewReason(event))}。点“编辑”补全后保存，就会从待确认里移出。</span></div>` : ""}
        <section class="detail-section">
          <h3 class="drawer-section-title">日程信息</h3>
          <dl class="detail-facts">
            ${facts.map((fact) => `<div class="detail-fact${fact.full ? " is-full" : ""}">
              <dt>${escapeHtml(fact.label)}</dt>
              <dd>${escapeHtml(fact.value)}</dd>
            </div>`).join("")}
          </dl>
        </section>
        ${userNotes ? `<section class="detail-section">
          <h3 class="drawer-section-title">我的备注</h3>
          <p class="detail-notes">${escapeHtml(userNotes)}</p>
        </section>` : ""}
        ${autoNotes.length ? `<details class="detail-disclosure">
          <summary>邮件提醒<span>${autoNotes.length} 条</span></summary>
          <ul class="note-list">${autoNotes.map((line) => `<li>${escapeHtml(line.replace(/^[-•·]\s*/, ""))}</li>`).join("")}</ul>
        </details>` : ""}
        <section class="detail-section detail-source">
          <div class="drawer-section-head">
            <h3 class="drawer-section-title">来源邮件</h3>
            ${sourceCount > 1 ? `<span class="drawer-section-note">合并了 ${sourceCount} 封相关邮件</span>` : ""}
          </div>
          ${event.source_subject ? `<details class="source-mail">
            <summary>
              <span class="source-mail-icon">${icon("mail", 14)}</span>
              <span class="source-summary-copy">
                <span class="source-subject">${escapeHtml(event.source_subject)}</span>
                <span class="source-meta">${escapeHtml(sourceMeta || "未知发件人")}</span>
              </span>
              <span class="source-toggle-icon">${icon("chevronDown", 15)}</span>
            </summary>
            <pre class="source-body">${escapeHtml(sourceBody || "这封邮件没有可显示的纯文本内容。")}</pre>
          </details>` : `<div class="source-empty">这条记录没有保留来源邮件正文。</div>`}
        </section>
      </div>
    </div>
    <div class="drawer-footer">
      ${footerLeft}
      <div class="drawer-footer-actions">
        <button class="button button-ghost" type="button" data-action="close-drawer">关闭</button>
        <button class="button button-primary" type="button" data-action="edit-event">编辑</button>
      </div>
    </div>`;
}

function renderDrawer() {
  if (!state.drawer) return;
  const { event, mode, loading, error } = state.drawer;

  if (loading) {
    el.drawer.innerHTML = `${drawerHeaderMarkup(event, mode, true, null)}
      <div class="drawer-scroll">
        <div class="drawer-loading">
          <div class="skeleton-line is-heading"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-line is-short"></div>
          <div class="skeleton-line" style="margin-top:30px"></div>
          <div class="skeleton-line"></div>
          <div class="skeleton-line is-short"></div>
        </div>
      </div>`;
    return;
  }

  if (error) {
    el.drawer.innerHTML = `${drawerHeaderMarkup(null, mode, false, error)}
      <div class="drawer-scroll">
        <div class="drawer-load-error">
          <div class="empty-illustration" style="margin-inline:auto">${icon("alert", 27)}</div>
          <h2 class="empty-title">没有读到这条记录</h2>
          <p>${escapeHtml(error)}</p>
          <button class="button button-ghost button-small" type="button" data-action="retry-drawer">重试</button>
        </div>
      </div>
      <div class="drawer-footer">
        <div class="drawer-footer-actions">
          <button class="button button-ghost" type="button" data-action="close-drawer">关闭</button>
        </div>
      </div>`;
    return;
  }

  if (!event) return;
  if (!state.drawer.editing) {
    renderEventDetail(event);
    return;
  }
  const kind = eventKind(event);
  const interview = kind === "interview";
  const examDate = dateInputValue(event.exam_start);
  const examStart = timeInputValue(event.exam_start, event.exam_time_known);
  const examEnd = timeInputValue(event.exam_end, true);
  const deadlineDate = dateInputValue(event.deadline);
  const deadlineTime = timeInputValue(event.deadline, event.deadline_time_known);
  const needsReview = mode === "edit" && isReviewEvent(event);

  const footerLeft = mode === "edit"
    ? `<div class="drawer-footer-left">
        <button class="text-button is-danger" type="button" data-action="delete-event" data-id="${event.id}">删除</button>
        <button class="text-button" type="button" data-action="toggle-ignore" data-id="${event.id}">${event.ignored ? "恢复显示" : "忽略这条"}</button>
      </div>`
    : "";

  el.drawer.innerHTML = `${drawerHeaderMarkup(event, mode, false, null)}
    <div class="drawer-scroll">
      <div class="drawer-body">
        ${needsReview ? `<div class="drawer-alert">${icon("alert", 14)}<span>${escapeHtml(reviewReason(event))}。补全后保存，就会从待确认里移出。</span></div>` : ""}
        <form id="event-form" data-event-id="${event.id || ""}" data-mode="${mode}">
          <section class="drawer-section">
            <div class="drawer-section-head">
              <h3 class="drawer-section-title">基本信息</h3>
            </div>
            <div class="form-grid">
              <div class="form-field">
                <label class="field-label" for="event-kind">记录类型</label>
                <select class="select" id="event-kind" name="kind">
                  <option value="exam" ${kind === "exam" ? "selected" : ""}>笔试 / 测评</option>
                  <option value="interview" ${kind === "interview" ? "selected" : ""}>面试</option>
                </select>
              </div>
              <div class="form-field" data-interview-round-field ${interview ? "" : "hidden"}>
                <label class="field-label" for="event-round">面试轮次</label>
                <input class="input" id="event-round" name="interview_round" type="text" value="${escapeHtml(event.interview_round || "")}" placeholder="一面 / 二面 / HR 面" maxlength="20">
              </div>
            </div>
            <div class="form-grid">
              <div class="form-field">
                <label class="field-label" for="event-company">公司<span class="required">*</span></label>
                <input class="input" id="event-company" name="company" type="text" value="${escapeHtml(event.company || "")}" placeholder="例如：字节跳动" maxlength="100" required>
              </div>
              <div class="form-field">
                <label class="field-label" for="event-role">岗位</label>
                <input class="input" id="event-role" name="role" type="text" value="${escapeHtml(event.role || "")}" placeholder="例如：后端开发工程师" maxlength="100">
              </div>
            </div>
          </section>

          <section class="drawer-section">
            <div class="drawer-section-head">
              <h3 class="drawer-section-title" data-kind-label-exam="考试时间" data-kind-label-interview="面试时间">${interview ? "面试时间" : "考试时间"}</h3>
            </div>
            <div class="form-grid is-3">
              <div class="form-field">
                <label class="field-label" for="event-exam-date" data-kind-label-exam="考试日期" data-kind-label-interview="面试日期">${interview ? "面试日期" : "考试日期"}</label>
                <input class="input" id="event-exam-date" name="exam_date" type="date" value="${examDate}">
              </div>
              <div class="form-field">
                <label class="field-label" for="event-exam-start">开始时间</label>
                <input class="input" id="event-exam-start" name="exam_start_time" type="time" value="${examStart}">
              </div>
              <div class="form-field">
                <label class="field-label" for="event-exam-end">结束时间</label>
                <input class="input" id="event-exam-end" name="exam_end_time" type="time" value="${examEnd}">
              </div>
            </div>
            <div class="form-grid is-3">
              <div class="form-field">
                <label class="field-label" for="event-deadline-date" data-kind-label-exam="截止日期" data-kind-label-interview="确认截止日期">${interview ? "确认截止日期" : "截止日期"}</label>
                <input class="input" id="event-deadline-date" name="deadline_date" type="date" value="${deadlineDate}">
              </div>
              <div class="form-field">
                <label class="field-label" for="event-deadline-time" data-kind-label-exam="截止时间" data-kind-label-interview="确认截止时间">${interview ? "确认截止时间" : "截止时间"}</label>
                <input class="input" id="event-deadline-time" name="deadline_time" type="time" value="${deadlineTime}">
              </div>
              <div class="form-field">
                <label class="field-label" for="event-duration"><span data-kind-label-exam="作答时长" data-kind-label-interview="面试时长">${interview ? "面试时长" : "作答时长"}</span><span class="field-suffix">分钟</span></label>
                <input class="input" id="event-duration" name="duration_minutes" type="number" min="1" max="1440" value="${event.duration_minutes ?? ""}" placeholder="${interview ? "例如 45" : "例如 120"}">
              </div>
            </div>
          </section>

          <section class="drawer-section">
            <div class="drawer-section-head">
              <h3 class="drawer-section-title" data-kind-label-exam="考试入口" data-kind-label-interview="面试入口">${interview ? "面试入口" : "考试入口"}</h3>
              <span class="drawer-section-note">链接和会议信息仅保存在本机</span>
            </div>
            <div class="form-grid">
              <div class="form-field">
                <label class="field-label" for="event-platform" data-kind-label-exam="考试平台" data-kind-label-interview="面试平台">${interview ? "面试平台" : "考试平台"}</label>
                <input class="input" id="event-platform" name="platform" type="text" value="${escapeHtml(event.platform || "")}" placeholder="${interview ? "腾讯会议 / Zoom / 飞书" : "牛客 / 赛码 / HackerRank"}" data-kind-placeholder-exam="牛客 / 赛码 / HackerRank" data-kind-placeholder-interview="腾讯会议 / Zoom / 飞书" maxlength="100">
              </div>
              <div class="form-field">
                <label class="field-label" for="event-mode" data-kind-label-exam="考试形式" data-kind-label-interview="面试形式">${interview ? "面试形式" : "考试形式"}</label>
                <select class="select" id="event-mode" name="mode">
                  <option value="unknown" ${event.mode === "unknown" ? "selected" : ""}>待确认</option>
                  <option value="online" ${event.mode === "online" ? "selected" : ""}>线上</option>
                  <option value="offline" ${event.mode === "offline" ? "selected" : ""}>线下</option>
                </select>
              </div>
            </div>
            <div class="form-grid">
              <div class="form-field is-full">
                <label class="field-label" for="event-url" data-kind-label-exam="考试链接" data-kind-label-interview="面试链接">${interview ? "面试链接" : "考试链接"}</label>
                <input class="input" id="event-url" name="exam_url" type="url" value="${escapeHtml(event.exam_url || "")}" placeholder="https://...">
              </div>
            </div>
            <details class="drawer-advanced">
              <summary>更多信息<span>口令与地点</span></summary>
              <div class="form-grid">
                <div class="form-field">
                  <label class="field-label" for="event-code" data-kind-label-exam="考试口令 / 邀请码" data-kind-label-interview="会议号 / 密码">${interview ? "会议号 / 密码" : "考试口令 / 邀请码"}</label>
                  <input class="input" id="event-code" name="access_code" type="text" value="${escapeHtml(event.access_code || "")}" placeholder="${interview ? "会议号、入会密码" : "没有可留空"}" data-kind-placeholder-exam="没有可留空" data-kind-placeholder-interview="会议号、入会密码" maxlength="80" autocomplete="off">
                </div>
                <div class="form-field">
                  <label class="field-label" for="event-location" data-kind-label-exam="考试地点" data-kind-label-interview="面试地点">${interview ? "面试地点" : "考试地点"}</label>
                  <input class="input" id="event-location" name="location" type="text" value="${escapeHtml(event.location || "")}" placeholder="${interview ? "线下面试时填写地址" : "线下考试时填写考点或地址"}" data-kind-placeholder-exam="线下考试时填写考点或地址" data-kind-placeholder-interview="线下面试时填写地址" maxlength="200">
                </div>
              </div>
            </details>
          </section>

          <section class="drawer-section">
            <div class="drawer-section-head">
              <h3 class="drawer-section-title">记录状态</h3>
            </div>
            <div class="form-grid">
              <div class="form-field">
                <label class="field-label" for="event-status">状态</label>
                <select class="select" id="event-status" name="status">
                  <option value="pending" ${event.status === "pending" ? "selected" : ""}>待参加</option>
                  <option value="done" ${event.status === "done" ? "selected" : ""}>已完成</option>
                  <option value="cancelled" ${event.status === "cancelled" ? "selected" : ""}>已取消</option>
                </select>
              </div>
              <div class="form-field is-full">
                <label class="field-label" for="event-notes">我的备注</label>
                <textarea class="textarea" id="event-notes" name="notes" placeholder="复习重点、设备测试、交通安排…" maxlength="5000">${escapeHtml(event.notes || "")}</textarea>
              </div>
            </div>
            <div class="form-error" data-form-error hidden></div>
          </section>
        </form>
      </div>
    </div>
    <div class="drawer-footer">
      ${footerLeft}
      <div class="drawer-footer-actions">
        <button class="button button-ghost" type="button" data-action="${mode === "edit" ? "cancel-edit" : "close-drawer"}">取消</button>
        <button class="button button-primary" type="submit" form="event-form" data-submit-event>${mode === "create" ? `添加${KIND_LABELS[kind]}` : "保存修改"}</button>
      </div>
    </div>`;
  applyEventKindUI(kind);
}

function applyEventKindUI(kind) {
  const interview = kind === "interview";
  document.querySelectorAll("[data-kind-label-exam]").forEach((node) => {
    const value = interview ? node.dataset.kindLabelInterview : node.dataset.kindLabelExam;
    if (value) node.textContent = value;
  });
  document.querySelectorAll("[data-kind-placeholder-exam]").forEach((node) => {
    const value = interview ? node.dataset.kindPlaceholderInterview : node.dataset.kindPlaceholderExam;
    if (value) node.setAttribute("placeholder", value);
  });
  const roundField = document.querySelector("[data-interview-round-field]");
  if (roundField) roundField.hidden = !interview;
  if (state.drawer?.mode === "create") {
    const title = document.querySelector("[data-kind-title]");
    if (title) title.textContent = `新的${KIND_LABELS[kind]}`;
    const submit = document.querySelector("[data-submit-event]");
    if (submit) submit.textContent = `添加${KIND_LABELS[kind]}`;
  } else if (state.drawer?.event && !state.drawer.event.is_demo) {
    const kicker = document.querySelector("[data-kind-kicker]");
    if (kicker) {
      kicker.textContent = interview
        ? "INTERVIEW DETAIL · 面试详情"
        : "EXAM DETAIL · 笔试详情";
    }
  }
  if (state.drawer?.event) state.drawer.event.kind = kind;
}

// ---------------------------------------------------------------------------
// Toast + confirm
// ---------------------------------------------------------------------------

function showToast(message, type = "success") {
  const toast = document.createElement("div");
  toast.className = `toast is-${type}`;
  toast.textContent = message;
  el.toast.append(toast);
  while (el.toast.children.length > 3) el.toast.firstElementChild?.remove();
  window.setTimeout(() => {
    toast.classList.add("is-leaving");
    window.setTimeout(() => toast.remove(), 180);
  }, type === "error" ? 6_200 : 4_200);
}

function showConfirm({
  title,
  message,
  confirmLabel = "确认",
  danger = true,
  iconName = "alert",
}) {
  const dialog = el.confirm;
  if (dialog.open) return Promise.resolve(false);
  dialog.querySelector("#confirm-title").textContent = title;
  dialog.querySelector("#confirm-message").textContent = message;
  const mark = dialog.querySelector("#confirm-mark");
  mark.className = `confirm-mark${danger ? " is-danger" : ""}`;
  mark.innerHTML = icon(iconName, 19);
  const confirmButton = dialog.querySelector("#confirm-button");
  confirmButton.textContent = confirmLabel;
  confirmButton.className = `button ${danger ? "button-danger" : "button-primary"}`;
  dialog.returnValue = "cancel";
  return new Promise((resolve) => {
    const onClose = () => resolve(dialog.returnValue === "confirm");
    dialog.addEventListener("close", onClose, { once: true });
    dialog.showModal();
  });
}

function setButtonBusy(button, busy, busyLabel = "处理中…") {
  if (!button) return;
  if (busy) {
    if (!button.dataset.originalHtml) button.dataset.originalHtml = button.innerHTML;
    button.disabled = true;
    button.innerHTML = `<span class="button-spinner"></span>${escapeHtml(busyLabel)}`;
  } else {
    button.disabled = false;
    if (button.dataset.originalHtml) {
      button.innerHTML = button.dataset.originalHtml;
      delete button.dataset.originalHtml;
    }
  }
}

function setFormError(form, message) {
  const box = form?.querySelector("[data-form-error]");
  if (box) {
    box.hidden = !message;
    box.textContent = message || "";
  }
}

// ---------------------------------------------------------------------------
// Sync orchestration
// ---------------------------------------------------------------------------

function accountViewHasDraft() {
  if (state.accountFormBusy || state.reauthAccountId) return true;
  const values = ["account-email", "account-password", "account-label"]
    .map((id) => document.getElementById(id)?.value?.trim())
    .filter(Boolean);
  const active = document.activeElement;
  return values.length > 0 || Boolean(active?.closest?.("#account-form, [data-reauth-form]"));
}

function aiSettingsViewHasDraft() {
  if (state.aiBusy) return true;
  if (!document.getElementById("ai-settings-form")) return false;
  const ai = state.aiSettings || {};
  const text = (id) => String(document.getElementById(id)?.value || "").trim();
  if (text("ai-api-key")) return true;
  if (text("ai-base-url") !== String(ai.base_url || "")) return true;
  if (text("ai-model") !== String(ai.model || "")) return true;
  if (Number(text("ai-max-calls") || 20) !== Number(ai.max_calls_per_sync || 20)) return true;
  return Boolean(document.activeElement?.closest?.("#ai-settings-form"));
}

function startSyncPolling() {
  if (state.syncPollTimer) return;
  state.syncPollTimer = window.setTimeout(pollSync, 1_300);
}

async function pollSync() {
  state.syncPollTimer = null;
  try {
    const accounts = await api("/api/accounts");
    state.accounts = accounts;
    updateSidebar();
    state.syncFailures = 0;
    if (accounts.some((account) => account.last_sync_status === "syncing")) {
      state.syncPollTimer = window.setTimeout(pollSync, 1_600);
      return;
    }

    const [events, meta] = await Promise.all([api("/api/events"), api("/api/meta")]);
    state.events = events;
    state.meta = meta;
    if (state.view === "accounts" && accountViewHasDraft()) {
      updateSidebar();
    } else if (state.view === "models" && aiSettingsViewHasDraft()) {
      updateSidebar();
    } else {
      renderCurrentView();
    }
    if (state.syncNotice) {
      const failed = accounts.filter((account) => account.last_sync_status === "error");
      if (failed.length) {
        showToast(`同步失败：${failed[0].last_sync_error || "请检查邮箱设置"}`, "error");
      } else {
        const created = accounts.reduce((sum, account) => sum + Number(account.last_sync_counts?.created || 0), 0);
        const createdExams = accounts.reduce((sum, account) => sum + Number(account.last_sync_counts?.created_exams || 0), 0);
        const createdInterviews = accounts.reduce((sum, account) => sum + Number(account.last_sync_counts?.created_interviews || 0), 0);
        const merged = accounts.reduce((sum, account) => sum + Number(account.last_sync_counts?.merged || 0), 0);
        const reclassified = accounts.reduce((sum, account) => sum + Number(account.last_sync_counts?.reclassified || 0), 0);
        const scanned = accounts.reduce((sum, account) => sum + Number(account.last_sync_counts?.scanned || 0), 0);
        const llmCalled = accounts.reduce((sum, account) => sum + Number(account.last_sync_counts?.llm_called || 0), 0);
        const llmMatched = accounts.reduce((sum, account) => sum + Number(account.last_sync_counts?.llm_matched || 0), 0);
        const llmErrors = accounts.reduce((sum, account) => sum + Number(account.last_sync_counts?.llm_errors || 0), 0);
        const parts = [];
        if (created) {
          parts.push(createdBreakdown({ created, created_exams: createdExams, created_interviews: createdInterviews }) || `新增 ${created} 场`);
        }
        if (reclassified) parts.push(`重新识别 ${reclassified} 条`);
        if (merged) parts.push(`合并 ${merged} 条提醒`);
        if (llmCalled) parts.push(`AI 识别 ${llmMatched}/${llmCalled} 条`);
        if (llmErrors) parts.push(`AI 调用失败 ${llmErrors} 次`);
        if (parts.length) {
          showToast(`同步完成，${parts.join("，")}`, "success");
        } else if (scanned) {
          showToast(`检查了 ${scanned} 封新邮件，没有发现新的笔试或面试`, "info");
        } else {
          showToast("同步完成，没有需要检查的新邮件", "info");
        }
      }
      state.syncNotice = false;
    }
  } catch (error) {
    state.syncFailures += 1;
    updateSidebar();
    if (state.syncFailures >= 3) {
      showToast(error.message || "同步状态获取失败，请刷新页面。", "error");
      return;
    }
    state.syncPollTimer = window.setTimeout(pollSync, 2_400);
  }
}

async function triggerAccountSync(accountId) {
  try {
    await api(`/api/accounts/${accountId}/sync`, { method: "POST" });
    state.syncNotice = true;
    state.syncFailures = 0;
    await refreshAccountsOnly();
    if (state.view === "accounts") renderCurrentView();
    else updateSidebar();
    startSyncPolling();
    showToast("已开始同步这个邮箱", "info");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function triggerAccountRescan(accountId) {
  const account = state.accounts.find((item) => item.id === Number(accountId));
  if (!account) return;
  const confirmed = await showConfirm({
    title: "重新识别最近的邮件？",
    message: `会重新读取 ${account.email} 当前同步范围内的邮件，补识别此前忽略的面试邀请。\n已有记录不会重复生成，手动修改过的内容不会被覆盖。`,
    confirmLabel: "开始重新识别",
    danger: false,
    iconName: "search",
  });
  if (!confirmed) return;
  try {
    await api(`/api/accounts/${accountId}/rescan`, { method: "POST" });
    state.syncNotice = true;
    state.syncFailures = 0;
    await refreshAccountsOnly();
    if (state.view === "accounts") renderCurrentView();
    else updateSidebar();
    startSyncPolling();
    showToast("已开始重新识别，完成后会自动刷新", "info");
  } catch (error) {
    showToast(error.message, "error");
  }
}

// ---------------------------------------------------------------------------
// Event actions
// ---------------------------------------------------------------------------

async function toggleEventDone(eventId, button = null) {
  const event = state.events.find((item) => item.id === Number(eventId));
  if (!event || state.quickBusy.has(event.id)) return;
  state.quickBusy.add(event.id);
  if (button) button.disabled = true;
  const nextStatus = event.status === "done" ? "pending" : "done";
  try {
    await api(`/api/events/${event.id}`, { method: "PATCH", body: { status: nextStatus } });
    await refreshData();
    showToast(nextStatus === "done" ? "已标记为完成" : "已移回待参加", "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    state.quickBusy.delete(event.id);
    if (button && document.contains(button)) button.disabled = false;
  }
}

async function toggleIgnoreEvent(eventId) {
  const event = state.drawer?.event || state.events.find((item) => item.id === Number(eventId));
  if (!event) return;
  const next = !event.ignored;
  try {
    await api(`/api/events/${event.id}`, { method: "PATCH", body: { ignored: next } });
    closeDrawer();
    await refreshData();
    showToast(next ? "已忽略这条记录" : "已恢复显示", next ? "info" : "success");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function deleteEventPermanently(eventId) {
  const event = state.drawer?.event || state.events.find((item) => item.id === Number(eventId));
  if (!event) return;
  const confirmed = await showConfirm({
    title: "删除这条日程记录？",
    message: `${displayCompany(event)} · ${displayRole(event)}\n删除后无法恢复，但不会影响原始邮件。`,
    confirmLabel: "删除记录",
    danger: true,
    iconName: "trash",
  });
  if (!confirmed) return;
  try {
    await api(`/api/events/${event.id}`, { method: "DELETE" });
    closeDrawer();
    await refreshData();
    showToast("记录已删除", "info");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function submitEventForm(form) {
  if (state.drawer?.saving) return;
  const mode = state.drawer?.mode || "edit";
  const submitButton = el.drawer.querySelector("[data-submit-event]");
  setFormError(form, "");
  const data = new FormData(form);
  const kind = String(data.get("kind") || "exam") === "interview" ? "interview" : "exam";
  const interviewRound = kind === "interview" ? String(data.get("interview_round") || "").trim() : "";
  const company = String(data.get("company") || "").trim();
  const examDate = String(data.get("exam_date") || "").trim();
  const examStartTime = String(data.get("exam_start_time") || "").trim();
  const examEndTime = String(data.get("exam_end_time") || "").trim();
  const deadlineDate = String(data.get("deadline_date") || "").trim();
  const deadlineTime = String(data.get("deadline_time") || "").trim();

  if (!company) {
    setFormError(form, "请填写公司名称。");
    form.querySelector("#event-company")?.focus();
    return;
  }
  if (!examDate && (examStartTime || examEndTime)) {
    setFormError(form, `填写${kind === "interview" ? "面试" : "考试"}时间前，请先选择日期。`);
    form.querySelector("#event-exam-date")?.focus();
    return;
  }
  if (examEndTime && !examStartTime) {
    setFormError(form, "填写结束时间前，请先填写开始时间。");
    form.querySelector("#event-exam-start")?.focus();
    return;
  }
  if (!deadlineDate && deadlineTime) {
    setFormError(form, "填写截止时间前，请先选择截止日期。");
    form.querySelector("#event-deadline-date")?.focus();
    return;
  }

  let examStart = null;
  let examEnd = null;
  let examTimeKnown = false;
  if (examDate) {
    examStart = `${examDate}T${examStartTime || "00:00"}`;
    examTimeKnown = Boolean(examStartTime);
    if (examEndTime) {
      const endDate = addDaysToKey(examDate, examEndTime <= examStartTime ? 1 : 0);
      examEnd = `${endDate}T${examEndTime}`;
    }
  }
  let deadline = null;
  let deadlineTimeKnown = false;
  if (deadlineDate) {
    deadline = `${deadlineDate}T${deadlineTime || "00:00"}`;
    deadlineTimeKnown = Boolean(deadlineTime);
  }
  const examUrlRaw = String(data.get("exam_url") || "").trim();
  if (examUrlRaw && !safeHttpUrl(examUrlRaw)) {
    setFormError(form, "链接需要以 http:// 或 https:// 开头。");
    form.querySelector("#event-url")?.focus();
    return;
  }

  const rawDuration = String(data.get("duration_minutes") || "").trim();
  const payload = {
    kind,
    interview_round: interviewRound || null,
    company,
    role: String(data.get("role") || "").trim(),
    exam_start: examStart,
    exam_end: examEnd,
    exam_time_known: examTimeKnown,
    deadline,
    deadline_time_known: deadlineTimeKnown,
    duration_minutes: rawDuration ? Number(rawDuration) : null,
    platform: String(data.get("platform") || "").trim() || null,
    exam_url: examUrlRaw || null,
    mode: String(data.get("mode") || "unknown"),
    location: String(data.get("location") || "").trim() || null,
    access_code: String(data.get("access_code") || "").trim() || null,
    status: String(data.get("status") || "pending"),
    notes: String(data.get("notes") || "").trim() || null,
  };

  if (state.drawer) state.drawer.saving = true;
  setButtonBusy(submitButton, true, "保存中…");
  try {
    if (mode === "create") {
      await api("/api/events", { method: "POST", body: payload });
    } else {
      await api(`/api/events/${state.drawer.id}`, { method: "PATCH", body: payload });
    }
    closeDrawer({ restoreFocus: false });
    await refreshData();
    showToast(mode === "create" ? `${KIND_LABELS[kind]}已添加` : "修改已保存", "success");
  } catch (error) {
    if (state.drawer) state.drawer.saving = false;
    setFormError(form, error.message);
    setButtonBusy(submitButton, false);
  }
}

// ---------------------------------------------------------------------------
// Account actions
// ---------------------------------------------------------------------------

async function submitAISettingsForm(form) {
  if (state.aiBusy) return;
  setFormError(form, "");
  const data = new FormData(form);
  const baseUrl = String(data.get("base_url") || "").trim();
  const model = String(data.get("model") || "").trim();
  const apiKey = String(data.get("api_key") || "").trim();
  const maxCalls = Number(data.get("max_calls_per_sync") || 20);

  if (baseUrl && !/^https?:\/\//i.test(baseUrl)) {
    setFormError(form, "接口地址需要以 http:// 或 https:// 开头。");
    form.querySelector("#ai-base-url")?.focus();
    return;
  }
  if (apiKey && (!baseUrl || !model)) {
    setFormError(form, "填写 API Key 时，请同时填写接口地址和模型名称。");
    (baseUrl ? form.querySelector("#ai-model") : form.querySelector("#ai-base-url"))?.focus();
    return;
  }
  if (!Number.isInteger(maxCalls) || maxCalls < 1 || maxCalls > 300) {
    setFormError(form, "每次同步调用次数需在 1 到 300 之间。");
    form.querySelector("#ai-max-calls")?.focus();
    return;
  }

  state.aiBusy = true;
  const submit = form.querySelector("button[type='submit']");
  setButtonBusy(submit, true, "保存中…");
  try {
    const saved = await api("/api/ai-settings", {
      method: "PUT",
      body: {
        base_url: baseUrl,
        model,
        api_key: apiKey || null,
        max_calls_per_sync: maxCalls,
      },
    });
    state.aiSettings = saved;
    state.aiBusy = false;
    renderCurrentView();
    showToast(saved.active ? "已启用大模型优先识别" : "已保存，当前使用本地规则", "success");
  } catch (error) {
    state.aiBusy = false;
    setFormError(form, error.message);
    setButtonBusy(submit, false);
  }
}

async function testAISettings() {
  if (state.aiBusy) return;
  state.aiBusy = true;
  const button = document.querySelector("[data-action='test-ai']");
  setButtonBusy(button, true, "测试中…");
  try {
    const result = await api("/api/ai-settings/test", { method: "POST" });
    showToast(result.message || "连接成功", "success");
  } catch (error) {
    showToast(error.message, "error");
  } finally {
    state.aiBusy = false;
    if (button && document.contains(button)) setButtonBusy(button, false);
  }
}

async function clearAIKeyWithConfirm() {
  const confirmed = await showConfirm({
    title: "删除连接？",
    message: "删除后将恢复为完全本地规则识别，不再向大模型接口发送邮件内容。",
    confirmLabel: "删除连接",
    danger: true,
    iconName: "key",
  });
  if (!confirmed) return;
  try {
    const saved = await api("/api/ai-settings", {
      method: "PUT",
      body: {
        base_url: state.aiSettings?.base_url || "",
        model: state.aiSettings?.model || "",
        max_calls_per_sync: state.aiSettings?.max_calls_per_sync || 20,
        clear_api_key: true,
      },
    });
    state.aiSettings = saved;
    renderCurrentView();
    showToast("连接已删除，当前使用本地规则", "info");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function submitAccountForm(form) {
  if (state.accountFormBusy) return;
  setFormError(form, "");
  const data = new FormData(form);
  const email = String(data.get("email") || "").trim();
  const password = String(data.get("password") || "");
  const label = String(data.get("label") || "").trim();
  const syncDays = Number(data.get("sync_days") || 30);
  const providerId = detectProviderId(email);
  const provider = providerById(providerId);

  if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    setFormError(form, "请输入有效的邮箱地址。");
    form.querySelector("#account-email")?.focus();
    return;
  }
  if (!provider) {
    setFormError(form, "暂时无法识别这个邮箱的服务商，请检查邮箱地址。");
    form.querySelector("#account-email")?.focus();
    return;
  }
  if (!password.trim()) {
    setFormError(form, `请填写${provider.auth_label}。`);
    form.querySelector("#account-password")?.focus();
    return;
  }

  const payload = {
    provider: provider.id,
    email,
    password,
    label,
    sync_days: syncDays,
    auto_sync: true,
    folder: "INBOX",
  };
  if (provider.custom) {
    const host = String(data.get("imap_host") || "").trim();
    const port = Number(data.get("imap_port") || 993);
    const folder = String(data.get("folder") || "INBOX").trim();
    if (!host) {
      setFormError(form, "请填写自定义 IMAP 服务器地址。");
      form.querySelector("#custom-host")?.focus();
      return;
    }
    if (!Number.isInteger(port) || port < 1 || port > 65535) {
      setFormError(form, "IMAP 端口需在 1 到 65535 之间。");
      return;
    }
    payload.imap_host = host;
    payload.imap_port = port;
    payload.folder = folder || "INBOX";
  }

  state.accountFormBusy = true;
  const submitButton = form.querySelector("[data-submit-account]");
  setButtonBusy(submitButton, true, "正在验证连接…");
  try {
    await api("/api/accounts", { method: "POST", body: payload });
    state.accountFormBusy = false;
    state.reauthAccountId = null;
    state.syncNotice = true;
    await loadAllData();
    renderCurrentView();
    startSyncPolling();
    showToast("邮箱已连接，正在同步最近的邮件", "success");
  } catch (error) {
    state.accountFormBusy = false;
    setFormError(form, error.message);
    setButtonBusy(submitButton, false);
  }
}

async function submitReauthForm(form) {
  const accountId = Number(form.dataset.reauthForm);
  const input = form.querySelector("input[name='password']");
  const password = String(input?.value || "").trim();
  if (!password) {
    setFormError(form, "请输入新的授权码。");
    input?.focus();
    return;
  }
  const submit = form.querySelector("button[type='submit']");
  setFormError(form, "");
  setButtonBusy(submit, true, "验证中…");
  try {
    await api(`/api/accounts/${accountId}`, { method: "PATCH", body: { password } });
    await refreshAccountsOnly();
    state.reauthAccountId = null;
    state.syncNotice = true;
    renderCurrentView();
    await triggerAccountSync(accountId);
    showToast("授权码已更新，正在验证同步", "success");
  } catch (error) {
    setFormError(form, error.message);
    setButtonBusy(submit, false);
  }
}

async function toggleAutoSync(accountId, checked, input) {
  try {
    const account = await api(`/api/accounts/${accountId}`, {
      method: "PATCH",
      body: { auto_sync: checked },
    });
    state.accounts = state.accounts.map((item) => item.id === accountId ? account : item);
    updateSidebar();
    showToast(checked ? "已开启自动同步" : "已关闭自动同步", "info");
  } catch (error) {
    if (input) input.checked = !checked;
    showToast(error.message, "error");
  }
}

async function deleteAccountWithConfirm(accountId) {
  const account = state.accounts.find((item) => item.id === Number(accountId));
  if (!account) return;
  const related = state.events.filter((event) => event.account_id === account.id).length;
  const confirmed = await showConfirm({
    title: "移除这个邮箱？",
    message: `将断开 ${account.email} 的连接${related ? `，并删除由它同步的 ${related} 条日程记录` : ""}。\n此操作无法撤销，但不会删除邮箱里的原始邮件。`,
    confirmLabel: "移除邮箱",
    danger: true,
    iconName: "trash",
  });
  if (!confirmed) return;
  try {
    await api(`/api/accounts/${account.id}`, { method: "DELETE" });
    state.reauthAccountId = null;
    await refreshData();
    showToast("邮箱已移除", "info");
  } catch (error) {
    showToast(error.message, "error");
  }
}

function focusAccountForm() {
  if (state.view !== "accounts") {
    navigate("accounts");
  }
  window.setTimeout(() => {
    document.getElementById("add-account-panel")?.scrollIntoView({ behavior: "smooth", block: "center" });
    document.getElementById("account-email")?.focus({ preventScroll: true });
  }, 120);
}

// ---------------------------------------------------------------------------
// Demo + refresh actions
// ---------------------------------------------------------------------------

async function loadDemoData() {
  try {
    const result = await api("/api/demo", { method: "POST" });
    await refreshData();
    if (result.inserted) showToast("已载入示例数据，连接邮箱后可以清除", "info");
    else showToast("示例数据已经在看板里了", "info");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function clearDemoData() {
  const confirmed = await showConfirm({
    title: "清除示例数据？",
    message: "只会删除标记为示例的记录，不会影响真实邮箱和手动添加的内容。",
    confirmLabel: "清除示例",
    danger: false,
    iconName: "sparkle",
  });
  if (!confirmed) return;
  try {
    await api("/api/demo", { method: "DELETE" });
    await refreshData();
    showToast("示例数据已清除", "success");
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function refreshEverything({ notify = false } = {}) {
  try {
    await refreshData();
    if (notify) showToast("看板已刷新", "success");
    if (state.accounts.some((account) => account.last_sync_status === "syncing")) startSyncPolling();
  } catch (error) {
    showToast(error.message, "error");
  }
}

// ---------------------------------------------------------------------------
// DOM event handling
// ---------------------------------------------------------------------------

function handleDocumentClick(event) {
  const target = event.target instanceof Element ? event.target : null;
  if (!target) return;

  const navTarget = target.closest("[data-nav]");
  if (navTarget) {
    event.preventDefault();
    navigate(navTarget.dataset.nav);
    return;
  }

  const kindTarget = target.closest("[data-kind-filter]");
  if (kindTarget) {
    event.preventDefault();
    state.kindFilter = kindTarget.dataset.kindFilter;
    updateLibraryKindUI();
    return;
  }

  const filterTarget = target.closest("[data-filter]");
  if (filterTarget) {
    event.preventDefault();
    state.libraryFilter = filterTarget.dataset.filter;
    document.querySelectorAll("[data-filter]").forEach((node) => {
      const active = node.dataset.filter === state.libraryFilter;
      node.classList.toggle("is-active", active);
      node.setAttribute("aria-selected", String(active));
    });
    const results = document.getElementById("library-results");
    if (results) results.innerHTML = renderLibraryResults();
    return;
  }

  const actionTarget = target.closest("[data-action]");
  if (!actionTarget) return;
  const action = actionTarget.dataset.action;
  const id = actionTarget.dataset.id;
  if (!action) return;

  if (action !== "toggle-password") event.preventDefault();

  switch (action) {
    case "add-event":
      openEventDrawer(null, { create: true });
      break;
    case "refresh":
      refreshEverything({ notify: true });
      break;
    case "sync-account":
      if (id) triggerAccountSync(Number(id));
      break;
    case "rescan-account":
      if (id) triggerAccountRescan(Number(id));
      break;
    case "test-ai":
      testAISettings();
      break;
    case "clear-ai-key":
      clearAIKeyWithConfirm();
      break;
    case "open-event":
      if (id) openEventDrawer(Number(id));
      break;
    case "toggle-done":
      if (id) toggleEventDone(Number(id), actionTarget);
      break;
    case "toggle-ignore":
      if (id) toggleIgnoreEvent(Number(id));
      break;
    case "delete-event":
      if (id) deleteEventPermanently(Number(id));
      break;
    case "close-drawer":
      closeDrawer();
      break;
    case "edit-event":
      if (state.drawer?.event) {
        state.drawer.editing = true;
        renderDrawer();
        focusDrawerEditor();
      }
      break;
    case "cancel-edit":
      if (!state.drawer) break;
      if (state.drawer.mode === "create") {
        closeDrawer();
      } else {
        state.drawer.editing = false;
        renderDrawer();
        focusDrawer();
      }
      break;
    case "retry-drawer":
      if (state.drawer?.id) openEventDrawer(state.drawer.id);
      break;
    case "focus-account-form":
      focusAccountForm();
      break;
    case "delete-account":
      if (id) deleteAccountWithConfirm(Number(id));
      break;
    case "toggle-reauth":
      state.reauthAccountId = state.reauthAccountId === Number(id) ? null : Number(id);
      renderCurrentView();
      if (state.reauthAccountId) {
        window.setTimeout(() => document.getElementById(`reauth-password-${state.reauthAccountId}`)?.focus(), 30);
      }
      break;
    case "cancel-reauth":
      state.reauthAccountId = null;
      renderCurrentView();
      break;
    case "clear-demo":
      clearDemoData();
      break;
    case "load-demo":
      loadDemoData();
      break;
    case "clear-search":
      state.libraryQuery = "";
      renderCurrentView();
      window.setTimeout(() => document.getElementById("library-search")?.focus(), 20);
      break;
    case "retry-boot":
      boot();
      break;
    case "toggle-password": {
      const input = document.getElementById(actionTarget.dataset.target || "");
      if (!input) break;
      const visible = input.type === "text";
      input.type = visible ? "password" : "text";
      actionTarget.innerHTML = icon(visible ? "eye" : "eyeOff", 15);
      actionTarget.setAttribute("aria-label", visible ? "显示授权码" : "隐藏授权码");
      break;
    }
    default:
      break;
  }
}

function handleDocumentSubmit(event) {
  const form = event.target;
  if (!(form instanceof HTMLFormElement)) return;
  if (form.id === "event-form") {
    event.preventDefault();
    submitEventForm(form);
  } else if (form.id === "account-form") {
    event.preventDefault();
    submitAccountForm(form);
  } else if (form.id === "ai-settings-form") {
    event.preventDefault();
    submitAISettingsForm(form);
  } else if (form.matches("[data-reauth-form]")) {
    event.preventDefault();
    submitReauthForm(form);
  }
}

function handleDocumentInput(event) {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLTextAreaElement) && !(target instanceof HTMLSelectElement)) {
    return;
  }
  if (target.id === "library-search") {
    state.libraryQuery = target.value;
    const results = document.getElementById("library-results");
    if (results) results.innerHTML = renderLibraryResults();
  }
  if (target.id === "event-deadline-date" && !target.value) {
    const deadlineTime = document.getElementById("event-deadline-time");
    if (deadlineTime instanceof HTMLInputElement) deadlineTime.value = "";
  }
  if (target.id === "account-email") {
    updateProviderUI(detectProviderId(target.value));
  }
  const form = target.closest("form");
  if (form && (form.id === "account-form" || form.id === "event-form" || form.id === "ai-settings-form" || form.matches("[data-reauth-form]"))) {
    setFormError(form, "");
  }
}

function handleDocumentChange(event) {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) && !(target instanceof HTMLSelectElement)) return;
  if (target.id === "event-kind" && target instanceof HTMLSelectElement) {
    applyEventKindUI(target.value);
    return;
  }
  if (!(target instanceof HTMLInputElement)) return;
  if (target.dataset.autosyncAccount) {
    toggleAutoSync(Number(target.dataset.autosyncAccount), target.checked, target);
  }
}

function handleDocumentKeydown(event) {
  if (event.key !== "Escape") return;
  if (el.confirm.open) return;
  if (state.drawer) {
    closeDrawer();
    return;
  }
  if (document.body.classList.contains("sidebar-open")) closeSidebar();
}

function trapDrawerFocus(event) {
  if (event.key !== "Tab" || !state.drawer) return;
  const focusable = [...el.drawer.querySelectorAll(
    'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])',
  )].filter((node) => node instanceof HTMLElement && node.offsetParent !== null);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable.at(-1);
  if (event.shiftKey && (document.activeElement === first || !el.drawer.contains(document.activeElement))) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function openSidebar() {
  el.sidebar.classList.add("is-open");
  el.sidebarBackdrop.hidden = false;
  document.body.classList.add("sidebar-open");
}

function closeSidebar() {
  el.sidebar.classList.remove("is-open");
  el.sidebarBackdrop.hidden = true;
  document.body.classList.remove("sidebar-open");
}

function bindStaticEvents() {
  document.addEventListener("click", handleDocumentClick);
  document.addEventListener("submit", handleDocumentSubmit);
  document.addEventListener("input", handleDocumentInput);
  document.addEventListener("change", handleDocumentChange);
  document.addEventListener("keydown", handleDocumentKeydown);
  document.addEventListener("keydown", trapDrawerFocus);
  window.addEventListener("hashchange", handleHashChange);
  el.drawerScrim.addEventListener("click", () => closeDrawer());
  el.sidebarBackdrop.addEventListener("click", closeSidebar);
  document.getElementById("mobile-menu")?.addEventListener("click", openSidebar);
  document.getElementById("sidebar-close")?.addEventListener("click", closeSidebar);
  el.confirm.addEventListener("click", (event) => {
    if (event.target === el.confirm) el.confirm.close("cancel");
  });
}

bindStaticEvents();
boot();
