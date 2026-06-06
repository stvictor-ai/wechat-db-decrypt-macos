const state = {
  contacts: [],
  activeUsername: "",
  activeView: "chat",
  activeAnalysis: null,
  lastMemoryQuery: "",
  overviewLoaded: false,
  snapshotStatus: null,
  aiReportCount: 100,
};

const el = {
  status: document.querySelector("#status"),
  contactList: document.querySelector("#contactList"),
  messages: document.querySelector("#messages"),
  analysis: document.querySelector("#analysis"),
  analysisMeta: document.querySelector("#analysisMeta"),
  messageMeta: document.querySelector("#messageMeta"),
  chatTitle: document.querySelector("#chatTitle"),
  chatMeta: document.querySelector("#chatMeta"),
  profileAvatar: document.querySelector("#profileAvatar"),
  contactSearch: document.querySelector("#contactSearch"),
  searchBtn: document.querySelector("#searchBtn"),
  refreshBtn: document.querySelector("#refreshBtn"),
  startDate: document.querySelector("#startDate"),
  endDate: document.querySelector("#endDate"),
  limitSelect: document.querySelector("#limitSelect"),
  navButtons: document.querySelectorAll(".nav-icon[data-view]"),
  overviewView: document.querySelector("#overviewView"),
  overviewTitle: document.querySelector("#overviewTitle"),
  overviewNote: document.querySelector("#overviewNote"),
  overviewYear: document.querySelector("#overviewYear"),
  overviewRefreshBtn: document.querySelector("#overviewRefreshBtn"),
  overviewContent: document.querySelector("#overviewContent"),
  chatView: document.querySelector("#chatView"),
  reportView: document.querySelector("#reportView"),
  privacyView: document.querySelector("#privacyView"),
  roadmapView: document.querySelector("#roadmapView"),
  reportTitle: document.querySelector("#reportTitle"),
  reportRange: document.querySelector("#reportRange"),
  reportContent: document.querySelector("#reportContent"),
  reportExportBtn: document.querySelector("#reportExportBtn"),
  privacyRefreshBtn: document.querySelector("#privacyRefreshBtn"),
  privacyContent: document.querySelector("#privacyContent"),
  memoryView: document.querySelector("#memoryView"),
  memoryForm: document.querySelector("#memoryForm"),
  memoryInput: document.querySelector("#memoryInput"),
  memoryContent: document.querySelector("#memoryContent"),
  snapshotBadge: document.querySelector("#snapshotBadge"),
  snapshotRefreshBtn: document.querySelector("#snapshotRefreshBtn"),
  aiView: document.querySelector("#aiView"),
  aiContactTitle: document.querySelector("#aiContactTitle"),
  aiProvider: document.querySelector("#aiProvider"),
  aiKeyInput: document.querySelector("#aiKeyInput"),
  aiKeySave: document.querySelector("#aiKeySave"),
  aiThread: document.querySelector("#aiThread"),
  aiForm: document.querySelector("#aiForm"),
  aiInput: document.querySelector("#aiInput"),
  aiSendBtn: document.querySelector("#aiSendBtn"),
  wipeModal: document.querySelector("#wipeModal"),
  wipeConfirmInput: document.querySelector("#wipeConfirmInput"),
  wipeConfirmBtn: document.querySelector("#wipeConfirmBtn"),
  wipeCancelBtn: document.querySelector("#wipeCancelBtn"),
  aiReportCard: document.querySelector("#aiReportCard"),
  aiReportBtn: document.querySelector("#aiReportBtn"),
  aiReportResult: document.querySelector("#aiReportResult"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function maskId(str) {
  if (!str) return str;
  if (str.startsWith('wxid_')) {
    const body = str.slice(5);
    if (body.length <= 5) return str;
    return 'wxid_' + body.slice(0, 2) + '***' + body.slice(-3);
  }
  if (/^1[3-9]\d{9}$/.test(str)) {
    return str.slice(0, 3) + '****' + str.slice(-4);
  }
  if (str.length > 6) {
    return str.slice(0, 2) + '***' + str.slice(-2);
  }
  return str;
}

function api(path) {
  return fetch(path).then((res) => {
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  });
}

function avatarText(name) {
  const text = (name || "?").trim();
  return escapeHtml(text.slice(0, 1).toUpperCase());
}

function setStatus(text) {
  el.status.textContent = text;
}

function formatDateRange(data) {
  if (data?.first_time && data?.last_time) return `${data.first_time} 至 ${data.last_time}`;
  const start = el.startDate.value || "开始";
  const end = el.endDate.value || "现在";
  return `${start} 至 ${end}`;
}

function switchView(view, updateHash = true) {
  state.activeView = view;
  for (const button of el.navButtons) {
    button.classList.toggle("active", button.dataset.view === view);
  }
  el.overviewView.classList.toggle("active", view === "overview");
  el.chatView.classList.toggle("active", view === "chat");
  el.memoryView.classList.toggle("active", view === "memory");
  el.reportView.classList.toggle("active", view === "report");
  el.aiView.classList.toggle("active", view === "ai");
  el.privacyView.classList.toggle("active", view === "privacy");
  el.roadmapView.classList.toggle("active", view === "roadmap");
  if (updateHash) {
    history.replaceState(null, "", view === "overview" ? location.pathname : `#${view}`);
  }
  if (view === "overview") loadOverview();
  if (view === "privacy") loadPrivacy();
  if (view === "ai") refreshAiContactTitle();
}

function debounce(fn, delay = 180) {
  let timer = null;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

function renderContacts(items) {
  el.contactList.innerHTML = items.map((item) => {
    const username = item.username || "";
    const name = item.display_name || username || "未知联系人";
    const subline = item.summary || (item.remark && item.nick_name ? item.nick_name : username);
    const isActive = username === state.activeUsername ? " active" : "";
    return `
      <button class="item${isActive}" data-username="${escapeHtml(username)}">
        <span class="avatar">${avatarText(name)}</span>
        <span class="item-main">
          <span class="item-row">
            <span class="name">${escapeHtml(name)}</span>
            <span class="meta">${escapeHtml(item.last_time || (item.is_group ? "群聊" : "联系人"))}</span>
          </span>
          <span class="summary">${escapeHtml(subline || maskId(username))}</span>
        </span>
      </button>
    `;
  }).join("");

  [...el.contactList.querySelectorAll(".item")].forEach((button) => {
    button.addEventListener("click", () => loadContact(button.dataset.username));
  });
}

function snapshotFreshnessText(data) {
  if (!data?.decrypted_exists) return "还没有聊天快照";
  if (!data.latest_session_time) return "快照时间未知";
  if (data.age_days === null || data.age_days === undefined) return `同步到 ${data.latest_session_time}`;
  if (data.age_days <= 1) return `已同步到 ${data.latest_session_time}`;
  return `快照约 ${Math.round(data.age_days)} 天前`;
}

function renderSnapshotStatus(data) {
  const text = snapshotFreshnessText(data);
  el.snapshotBadge.textContent = text;
  el.snapshotBadge.title = data?.decrypted_exists
    ? `联系人 ${data.contact_count || 0} 位，消息库 ${data.message_db_count || 0} 个，数据约 ${data.decrypted_size_gb || 0} GB`
    : "需要先生成本地聊天快照";
  el.snapshotBadge.classList.toggle("stale", Boolean(data?.age_days && data.age_days > 7));
}

function needsOnboarding(data) {
  return data && (!data.decrypted_exists || data.contact_count === 0);
}

function renderOnboarding(data) {
  const steps = [
    {
      key: "sqlcipher",
      title: "安装 sqlcipher",
      done: data.sqlcipher_available,
      detail: "用于解密微信本地数据库。",
      command: "brew install sqlcipher",
    },
    {
      key: "keys",
      title: "提取密钥",
      done: data.keys_exists,
      detail: "从微信进程内存中提取数据库密钥。需要先打开微信并登录，提取过程可能需要临时关闭 SIP。",
      command: "sudo python3 find_key_memscan.py",
    },
    {
      key: "snapshot",
      title: "生成聊天快照",
      done: data.decrypted_exists && data.contact_count > 0,
      detail: "将加密的微信数据库解密到本地快照。也可以使用桌面启动器的「刷新聊天快照」按钮。",
      command: "python3 decrypt_db.py",
    },
  ];

  const stepsHtml = steps
    .map(
      (s) => `
    <div class="onboarding-step ${s.done ? "done" : ""}">
      <span class="onboarding-dot">${s.done ? "✓" : steps.indexOf(s) + 1}</span>
      <div class="onboarding-step-body">
        <strong>${escapeHtml(s.title)}</strong>
        <p>${escapeHtml(s.detail)}</p>
        ${s.done ? "" : `<code class="onboarding-cmd">${escapeHtml(s.command)}</code>`}
        ${s.done ? '<span class="onboarding-done-label">已完成</span>' : ""}
      </div>
    </div>`
    )
    .join("");

  const allDone = steps.every((s) => s.done);

  el.overviewTitle.textContent = allDone ? "即将就绪" : "首次使用引导";
  el.overviewNote.textContent = allDone
    ? "所有依赖已就绪，请刷新页面查看数据。"
    : "完成以下步骤后即可开始分析你的微信聊天记录。";

  el.overviewContent.className = "overview-content";
  el.overviewContent.innerHTML = `
    <div class="onboarding-guide">
      <div class="onboarding-steps">${stepsHtml}</div>
      <div class="onboarding-footer">
        <p>所有数据仅在本机处理，不会上传到任何服务器。</p>
        <p>详细说明请参阅项目 README 和「普通用户使用说明」。</p>
      </div>
    </div>`;
}

function setupYearOptions() {
  const current = new Date().getFullYear();
  const years = [current, current - 1, current - 2, current - 3];
  el.overviewYear.innerHTML = years.map((year) => `<option value="${year}">${year}</option>`).join("");
}

async function loadContacts() {
  const query = el.contactSearch.value.trim();
  setStatus(query ? "正在搜索" : "正在载入联系人");
  const data = await api(`/api/contacts?q=${encodeURIComponent(query)}&limit=300`);
  state.contacts = data.contacts || [];
  renderContacts(state.contacts);
  setStatus(`${state.contacts.length} 位联系人`);
  if (!state.activeUsername && state.contacts[0]) {
    loadContact(state.contacts[0].username);
  }
}

function setActiveContact(username, data) {
  state.activeUsername = username;
  [...el.contactList.querySelectorAll(".item")].forEach((item) => {
    item.classList.toggle("active", item.dataset.username === username);
  });
  const display = data?.display_name || username;
  el.chatTitle.textContent = display;
  el.profileAvatar.textContent = avatarText(display);
  el.chatMeta.textContent = `${username}${data?.is_group ? " · 群聊" : ""}`;
  refreshAiContactTitle();
}

async function loadContact(username) {
  if (!username) return;
  setActiveContact(username);
  el.messages.className = "messages empty";
  el.messages.innerHTML = "<span>正在载入</span>";
  el.analysis.className = "analysis empty";
  el.analysis.innerHTML = "<span>正在分析</span>";

  const params = new URLSearchParams({
    username,
    limit: el.limitSelect.value,
    start_date: el.startDate.value,
    end_date: el.endDate.value,
  });
  const [chat, analysis] = await Promise.all([
    api(`/api/chat?${params.toString()}`),
    api(`/api/analysis?${new URLSearchParams({
      username,
      limit: "2000",
      start_date: el.startDate.value,
      end_date: el.endDate.value,
    }).toString()}`),
  ]);

  setActiveContact(username, chat);
  el.messageMeta.textContent = `${chat.messages.length} 条消息`;
  renderMessages(chat.messages || []);
  renderAnalysis(analysis);
  renderReport(analysis);
}

const MSG_ICONS = {
  "图片": "📷", "语音": "🎤", "视频": "🎬",
  "表情": "😄", "位置": "📍", "名片": "👤",
  "通话": "📞", "链接/文件": "📎",
  "系统": "ℹ️", "撤回": "↩️",
};

function renderMsgBody(msg) {
  const type = msg.type || "文本";
  const text = msg.text || "";
  if (type === "文本") return `<div class="body">${escapeHtml(text)}</div>`;
  const icon = MSG_ICONS[type] || "•";
  if (type === "语音") {
    const dur = msg.duration ? ` ${Math.round(msg.duration)}″` : "";
    return `<div class="body body-media">${icon}${dur}</div>`;
  }
  const label = text.replace(/^\[|\]$/g, "") || type;
  return `<div class="body body-media">${icon} ${escapeHtml(label)}</div>`;
}

function renderMessages(messages) {
  if (!messages.length) {
    el.messages.className = "messages empty";
    el.messages.innerHTML = "<span>暂无聊天记录</span>";
    return;
  }

  let lastDay = "";
  const html = [];
  for (const msg of messages) {
    const day = (msg.time || "").slice(0, 10);
    if (day && day !== lastDay) {
      html.push(`<div class="day">${escapeHtml(day)}</div>`);
      lastDay = day;
    }
    const mine = Boolean(msg.is_mine);
    const isSystem = msg.type === "系统";
    if (isSystem) {
      html.push(`<div class="system-row">${escapeHtml(msg.text || "")}</div>`);
      continue;
    }
    html.push(`
      <div class="bubble-row${mine ? " mine" : ""}">
        <div class="bubble">
          ${msg.sender ? `<div class="sender">${escapeHtml(msg.sender)}</div>` : ""}
          ${renderMsgBody(msg)}
          <div class="time">${escapeHtml((msg.time || "").slice(11))}</div>
        </div>
      </div>
    `);
  }
  el.messages.className = "messages";
  el.messages.innerHTML = html.join("");
  el.messages.scrollTop = el.messages.scrollHeight;
}

function metric(label, value, hint = "") {
  return `
    <div class="metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      ${hint ? `<small>${escapeHtml(hint)}</small>` : ""}
    </div>
  `;
}

function bar(label, value, max) {
  const width = max ? Math.max(4, Math.round(value * 100 / max)) : 0;
  return `
    <div class="bar-row">
      <span>${escapeHtml(label)}</span>
      <div class="bar-track"><i style="width:${width}%"></i></div>
      <strong>${escapeHtml(value)}</strong>
    </div>
  `;
}

function chips(items, key, valueKey) {
  if (!items?.length) return `<p class="muted">暂无足够数据</p>`;
  return `<div class="chips">${items.map((item) => (
    `<span>${escapeHtml(item[key])}<b>${escapeHtml(item[valueKey])}</b></span>`
  )).join("")}</div>`;
}

function listRows(items, labelKey, valueKey) {
  if (!items?.length) return `<p class="muted">暂无足够数据</p>`;
  const max = Math.max(...items.map((item) => item[valueKey]), 1);
  return items.map((item) => bar(item[labelKey], item[valueKey], max)).join("");
}

function relationScore(data) {
  if (data?.relationship_score) return data.relationship_score;
  if (!data?.total_messages) return 0;
  const volume = Math.min(35, Math.log10(data.total_messages + 1) * 12);
  const days = Math.min(28, data.active_days * 1.8);
  const balance = data.total_messages
    ? Math.max(0, 22 - Math.abs((data.mine_share || 0) - 50) * 0.55)
    : 0;
  const recency = data.last_time ? 12 : 0;
  return Math.max(1, Math.min(99, Math.round(volume + days + balance + recency)));
}

function scoreLabel(score) {
  if (state.activeAnalysis?.relationship_score_label && state.activeAnalysis.relationship_score === score) {
    return state.activeAnalysis.relationship_score_label;
  }
  if (score >= 78) return "稳定活跃";
  if (score >= 55) return "有来有往";
  if (score >= 30) return "轻量联系";
  return "样本较少";
}

function dimensionRows(items) {
  if (!items?.length) return `<p class="muted">暂无足够数据</p>`;
  return items.map((item) => `
    <div class="dimension-row">
      <div>
        <strong>${escapeHtml(item.name)}</strong>
        <span>${escapeHtml(item.evidence)}</span>
      </div>
      <div class="dimension-score">
        <em>${escapeHtml(item.label)}</em>
        <b>${escapeHtml(item.score)}</b>
      </div>
      <div class="bar-track"><i style="width:${Math.max(4, item.score)}%"></i></div>
    </div>
  `).join("");
}

function insightCards(items) {
  if (!items?.length) return `<p class="muted">暂无足够数据</p>`;
  return items.map((item) => `
    <section class="insight-card">
      <h5>${escapeHtml(item.title)}</h5>
      <p>${escapeHtml(item.body)}</p>
    </section>
  `).join("");
}

function renderAnalysis(data) {
  state.activeAnalysis = data;
  if (!data || !data.total_messages) {
    el.analysis.className = "analysis empty";
    el.analysis.innerHTML = "<span>暂无足够数据</span>";
    el.analysisMeta.textContent = "";
    return;
  }

  el.analysis.className = "analysis";
  el.analysisMeta.textContent = data.first_time && data.last_time
    ? `${data.first_time} 至 ${data.last_time}`
    : "";

  const typeMax = Math.max(...(data.top_types || []).map((item) => item.count), 1);
  const senderMax = Math.max(...(data.top_senders || []).map((item) => item.count), 1);
  const dayMax = Math.max(...(data.top_days || []).map((item) => item.count), 1);

  el.analysis.innerHTML = `
    <section class="relationship-note">
      <h4>关系判断</h4>
      <p>${escapeHtml(data.relationship_note || "暂无足够信息判断你们的关系。")}</p>
    </section>

    <section class="metrics">
      ${metric("消息总量", data.total_messages)}
      ${metric("活跃天数", data.active_days)}
      ${metric("日均消息", data.avg_per_active_day)}
      ${metric("活跃时段", data.busiest_hour || "-", `${data.busiest_hour_count || 0} 条`)}
    </section>

    <section class="analysis-block">
      <h4>对话占比</h4>
      ${data.is_group
        ? chips(data.top_senders, "name", "count")
        : `
          ${bar("我", data.mine_messages, data.total_messages)}
          ${bar(data.display_name, data.their_messages, data.total_messages)}
        `}
    </section>

    <section class="analysis-block">
      <h4>消息类型</h4>
      ${(data.top_types || []).map((item) => bar(item.name, item.count, typeMax)).join("")}
    </section>

    <section class="analysis-block">
      <h4>高频日期</h4>
      ${(data.top_days || []).map((item) => bar(item.date, item.count, dayMax)).join("") || `<p class="muted">暂无足够数据</p>`}
    </section>

    <section class="analysis-block">
      <h4>常见关键词</h4>
      ${chips(data.top_terms, "term", "count")}
    </section>

    ${data.is_group ? `
      <section class="analysis-block">
        <h4>群内发言人</h4>
        ${(data.top_senders || []).map((item) => bar(item.name, item.count, senderMax)).join("") || `<p class="muted">暂无足够数据</p>`}
      </section>
    ` : ""}
  `;
}

function renderReport(data) {
  const display = data?.display_name || state.activeUsername || "选择一个联系人";
  el.reportTitle.textContent = state.activeUsername ? `我和 ${display}` : "选择一个联系人";
  el.reportRange.textContent = data?.total_messages ? formatDateRange(data) : "选择联系人后生成完整报告";
  el.reportExportBtn.disabled = !(data && data.total_messages && state.activeUsername);

  if (!data || !data.total_messages) {
    el.reportContent.className = "report-content empty";
    el.reportContent.innerHTML = "<span>暂无足够数据生成关系报告。</span>";
    return;
  }

  const score = relationScore(data);
  const topDay = data.top_days?.[0];
  const topTerm = data.top_terms?.[0];
  const primaryType = data.top_types?.[0];
  const profile = data.relationship_profile || {};
  const voice = data.mine_share >= 65
    ? "你在这段关系里更常发起表达。"
    : data.their_share >= 65
      ? `${data.display_name} 在这段关系里更常发起表达。`
      : "你们的对话占比比较均衡。";

  el.reportContent.className = "report-content";
  el.reportContent.innerHTML = `
    <section class="report-card report-summary">
      <div>
        <span>关系温度</span>
        <strong>${score}</strong>
        <em>${scoreLabel(score)}</em>
      </div>
      <div class="profile-copy">
        <span>关系类型</span>
        <h4>${escapeHtml(profile.label || "关系样本")}</h4>
        <b>置信度：${escapeHtml(profile.confidence || "中")}</b>
        <p>${escapeHtml(profile.summary || data.relationship_note)}</p>
      </div>
    </section>

    <section class="report-grid">
      ${metric("消息总量", data.total_messages)}
      ${metric("活跃天数", data.active_days)}
      ${metric("互动占比", `${data.mine_share}% / ${data.their_share}%`, "我 / 对方")}
      ${metric("常聊时段", data.busiest_hour || "-", `${data.busiest_hour_count || 0} 条`)}
    </section>

    <section class="report-card">
      <h4>社交关系解读</h4>
      <p>${escapeHtml(voice)} ${topDay ? `高频互动日期是 ${escapeHtml(topDay.date)}，当天共有 ${topDay.count} 条消息。` : ""} ${topTerm ? `常见关键词里最突出的是“${escapeHtml(topTerm.term)}”。` : ""}</p>
    </section>

    <section class="insight-grid">
      ${insightCards(data.social_insights)}
    </section>

    <section class="report-card">
      <h4>关系维度</h4>
      ${dimensionRows(data.relationship_dimensions)}
    </section>

    <section class="report-two-col">
      <section class="report-card">
        <h4>互动节奏</h4>
        ${listRows(data.top_days, "date", "count")}
      </section>
      <section class="report-card">
        <h4>消息构成</h4>
        ${listRows(data.top_types, "name", "count")}
        ${primaryType ? `<p class="muted">主要消息类型：${escapeHtml(primaryType.name)}</p>` : ""}
      </section>
    </section>

    <section class="report-card">
      <h4>常见关键词</h4>
      ${chips(data.top_terms, "term", "count")}
    </section>
  `;
}

function overviewMetric(label, value, hint = "") {
  return `
    <section class="overview-metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
      ${hint ? `<em>${escapeHtml(hint)}</em>` : ""}
    </section>
  `;
}

function compactTerms(items) {
  if (!items?.length) return "暂无关键词";
  return items.slice(0, 4).map((item) => item.term || item.name).join("、");
}

function overviewList(title, items, valueText) {
  if (!items?.length) {
    return `<section class="overview-card"><h4>${escapeHtml(title)}</h4><p class="muted">暂无足够数据</p></section>`;
  }
  return `
    <section class="overview-card">
      <h4>${escapeHtml(title)}</h4>
      <div class="overview-list">
        ${items.map((item) => `
          <button class="overview-item" data-username="${escapeHtml(item.username)}">
            <span class="avatar">${avatarText(item.display_name)}</span>
            <span>
              <strong>${escapeHtml(item.display_name)}</strong>
              <em>${escapeHtml(item.relationship_type || item.summary || "")}</em>
            </span>
            <b>${escapeHtml(valueText(item))}</b>
          </button>
        `).join("")}
      </div>
    </section>
  `;
}

function renderMonthBars(items) {
  const max = Math.max(...(items || []).map((item) => item.count), 1);
  return `
    <section class="overview-card">
      <h4>月份分布</h4>
      <div class="month-grid">
        ${(items || []).map((item) => `
          <div class="month-bar">
            <i style="height:${Math.max(4, Math.round(item.count * 100 / max))}%"></i>
            <span>${escapeHtml(item.month.slice(5))}</span>
          </div>
        `).join("")}
      </div>
    </section>
  `;
}

function renderOverview(data) {
  el.overviewTitle.textContent = `${data.year} 年关系总览`;
  el.overviewNote.textContent = data.source_note || "基于本地聊天快照生成。";

  const highlights = data.highlights || {};
  const topTerm = highlights.top_term ? `${highlights.top_term.term} · ${highlights.top_term.count}` : "暂无";
  el.overviewContent.className = "overview-content";
  el.overviewContent.innerHTML = `
    <section class="overview-metrics">
      ${overviewMetric("分析联系人", data.analyzed_count, `候选 ${data.candidate_count}`)}
      ${overviewMetric("年度消息", data.total_messages)}
      ${overviewMetric("联系人日均", data.avg_active_days_per_contact, "活跃天数")}
      ${overviewMetric("年度关键词", topTerm)}
    </section>

    <section class="overview-highlight-grid">
      ${overviewMetric("聊得最多", highlights.most_active?.display_name || "暂无", highlights.most_active ? `${highlights.most_active.total_messages} 条` : "")}
      ${overviewMetric("关系温度最高", highlights.warmest?.display_name || "暂无", highlights.warmest ? `${highlights.warmest.relationship_score} 分` : "")}
      ${overviewMetric("连续互动最长", highlights.longest_streak?.display_name || "暂无", highlights.longest_streak ? `${highlights.longest_streak.longest_streak} 天` : "")}
      ${overviewMetric("夜聊占比最高", highlights.late_night?.display_name || "暂无", highlights.late_night ? `${highlights.late_night.night_share}%` : "")}
    </section>

    <section class="overview-two-col">
      ${overviewList("聊得最多的人", data.top_active, (item) => `${item.total_messages} 条`)}
      ${overviewList("关系温度最高", data.top_relationships, (item) => `${item.relationship_score} 分`)}
    </section>

    <section class="overview-two-col">
      ${overviewList("连续互动最长", data.top_continuity, (item) => `${item.longest_streak} 天`)}
      ${overviewList("夜间聊天较多", data.top_late_night, (item) => `${item.night_share}%`)}
    </section>

    <section class="overview-two-col">
      ${renderMonthBars(data.month_counts)}
      <section class="overview-card">
        <h4>年度高频词</h4>
        <div class="chips">${(data.top_terms || []).map((item) => `<span>${escapeHtml(item.term)}<b>${escapeHtml(item.count)}</b></span>`).join("") || "<p class='muted'>暂无足够数据</p>"}</div>
        <p class="overview-note">这些关键词来自最近活跃联系人样本，适合做回忆入口，不适合作为完整词频统计。</p>
      </section>
    </section>
  `;

  for (const button of el.overviewContent.querySelectorAll(".overview-item")) {
    button.addEventListener("click", () => {
      const username = button.dataset.username;
      if (username) loadContact(username).then(() => switchView("report"));
    });
  }
}

async function loadOverview(force = false) {
  if (needsOnboarding(state.snapshotStatus)) {
    renderOnboarding(state.snapshotStatus);
    return;
  }
  if (state.overviewLoaded && !force) return;
  state.overviewLoaded = true;
  el.overviewContent.className = "overview-content empty";
  el.overviewContent.innerHTML = "<span>正在生成年度总览</span>";
  try {
    const params = new URLSearchParams({
      year: el.overviewYear.value || String(new Date().getFullYear()),
      limit: "24",
      sample_limit: "1200",
    });
    const data = await api(`/api/overview?${params.toString()}`);
    renderOverview(data);
  } catch (err) {
    state.overviewLoaded = false;
    el.overviewContent.innerHTML = `<span>${escapeHtml(err.message)}</span>`;
  }
}

function exportReport() {
  if (!state.activeUsername) return;
  const params = new URLSearchParams({
    username: state.activeUsername,
    limit: "2000",
    start_date: el.startDate.value,
    end_date: el.endDate.value,
  });
  window.open(`/api/report.md?${params.toString()}`, "_blank");
}

function renderMemoryResults(data) {
  const results = data.results || [];
  const method = data.method === "fts_match" ? "全文索引" : data.method === "fts_content" ? "内容索引" : "逐表扫描";
  if (!state.lastMemoryQuery) {
    el.memoryContent.className = "memory-content empty";
    el.memoryContent.innerHTML = "<span>输入关键词后，会在本地聊天快照里搜索。</span>";
    return;
  }
  if (!results.length) {
    el.memoryContent.className = "memory-content empty";
    el.memoryContent.innerHTML = `<span>没有找到“${escapeHtml(state.lastMemoryQuery)}”相关记录。</span>`;
    return;
  }

  el.memoryContent.className = "memory-content";
  el.memoryContent.innerHTML = `
    <div class="memory-meta">找到 ${results.length} 条结果，搜索方式：${escapeHtml(method)}</div>
    <div class="memory-results">
      ${results.map((item) => `
        <button class="memory-item" data-username="${escapeHtml(item.username)}">
          <span class="avatar">${avatarText(item.display_name || item.username)}</span>
          <span class="memory-main">
            <span class="memory-row">
              <strong>${escapeHtml(item.display_name || item.username || "未知联系人")}</strong>
              <em>${escapeHtml(item.time || "")}</em>
            </span>
            ${item.sender ? `<span class="memory-sender">${escapeHtml(item.sender)}</span>` : ""}
            <span class="memory-text">${escapeHtml(item.text || "")}</span>
          </span>
        </button>
      `).join("")}
    </div>
  `;

  for (const button of el.memoryContent.querySelectorAll(".memory-item")) {
    button.addEventListener("click", () => {
      const username = button.dataset.username;
      if (username) {
        loadContact(username).then(() => switchView("chat"));
      }
    });
  }
}

async function searchMemory() {
  const query = el.memoryInput.value.trim();
  state.lastMemoryQuery = query;
  if (!query) {
    renderMemoryResults({ results: [] });
    return;
  }
  el.memoryContent.className = "memory-content empty";
  el.memoryContent.innerHTML = "<span>正在本地搜索</span>";
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(query)}&limit=80&contacts_only=1`);
    renderMemoryResults(data);
  } catch (err) {
    el.memoryContent.innerHTML = `<span>${escapeHtml(err.message)}</span>`;
  }
}

function privacyBadge(ok) {
  return `<b class="${ok ? "ok" : "warn"}">${ok ? "正常" : "注意"}</b>`;
}

function renderPrivacy(data) {
  const sizeGb = data.decrypted_size_gb ? `${data.decrypted_size_gb} GB` : "0 GB";
  el.privacyContent.className = "privacy-content";
  el.privacyContent.innerHTML = `
    <section class="privacy-grid">
      <section class="privacy-card">
        <h4>本地访问 ${privacyBadge(data.host_is_local)}</h4>
        <p>网页服务绑定在 ${escapeHtml(data.host)}，默认只能在本机打开。</p>
      </section>
      <section class="privacy-card">
        <h4>聊天快照 ${privacyBadge(data.decrypted_exists)}</h4>
        <p>当前解密数据约 ${escapeHtml(sizeGb)}，最近会话时间：${escapeHtml(data.latest_session_time || "未知")}。</p>
      </section>
      <section class="privacy-card">
        <h4>密钥文件 ${privacyBadge(!data.keys_tracked)}</h4>
        <p>${data.keys_exists ? "检测到 wechat_keys.json，请不要上传到 GitHub。" : "未检测到密钥文件。"}</p>
      </section>
      <section class="privacy-card">
        <h4>发布检查 ${privacyBadge(data.gitignore_present)}</h4>
        <p>发布前确认没有提交密钥、解密数据库、导出文件、真实聊天截图。</p>
      </section>
    </section>

    <section class="privacy-card">
      <h4>建议操作</h4>
      <ul>
        <li>公开仓库前运行：git status --short</li>
        <li>确认这些目录不进仓库：wechat_keys.json、decrypted/、exported/、.claude/</li>
        <li>如果要截图展示，使用合成数据或打码后的截图。</li>
        <li>不要把本工具用于未经授权的设备或聊天记录。</li>
      </ul>
    </section>

    <section class="privacy-card privacy-danger-card">
      <h4>清理本地数据</h4>
      <p>删除本机所有解密数据库和导出文件（decrypted/ 和 exported/）。操作不可撤销，如需再次使用请重新运行解密。</p>
      <button id="wipeOpenBtn" class="danger-btn">一键清理解密数据</button>
    </section>
  `;
}

async function loadPrivacy() {
  el.privacyContent.className = "privacy-content empty";
  el.privacyContent.innerHTML = "<span>正在检查本地安全状态</span>";
  try {
    const data = await api("/api/privacy");
    renderPrivacy(data);
  } catch (err) {
    el.privacyContent.innerHTML = `<span>${escapeHtml(err.message)}</span>`;
  }
}

// ─────────────────────────────────────── Wipe ──────────────────────────────

function openWipeModal() {
  el.wipeConfirmInput.value = "";
  el.wipeConfirmBtn.disabled = true;
  el.wipeModal.hidden = false;
  el.wipeConfirmInput.focus();
}

function closeWipeModal() {
  el.wipeModal.hidden = true;
}

async function confirmWipe() {
  el.wipeConfirmBtn.disabled = true;
  el.wipeConfirmBtn.textContent = "正在清理…";
  try {
    const res = await fetch("/api/wipe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: "WIPE" }),
    });
    const data = await res.json();
    closeWipeModal();
    if (data.success) {
      const what = data.wiped?.join("、") || "数据";
      alert(`已清理：${what}`);
      state.overviewLoaded = false;
      await loadSnapshotStatus();
      loadContacts().catch(() => {});
    } else {
      alert("清理失败：" + (data.message || data.error));
    }
  } catch (err) {
    alert("请求失败：" + err.message);
  } finally {
    el.wipeConfirmBtn.textContent = "确认清理";
    el.wipeConfirmBtn.disabled = false;
  }
}

el.wipeConfirmInput.addEventListener("input", () => {
  el.wipeConfirmBtn.disabled = el.wipeConfirmInput.value !== "WIPE";
});
el.wipeConfirmBtn.addEventListener("click", confirmWipe);
el.wipeCancelBtn.addEventListener("click", closeWipeModal);
el.wipeModal.addEventListener("click", (e) => { if (e.target === el.wipeModal) closeWipeModal(); });
document.addEventListener("click", (e) => {
  if (e.target?.id === "wipeOpenBtn") openWipeModal();
});

// ─────────────────────────────────────── AI ────────────────────────────────

const AI_KEY_STORAGE = "wechat_ai_key";
const AI_PROV_STORAGE = "wechat_ai_provider";

function loadAiKey() {
  const key = localStorage.getItem(AI_KEY_STORAGE) || "";
  const prov = localStorage.getItem(AI_PROV_STORAGE) || "anthropic";
  el.aiKeyInput.value = key;
  el.aiProvider.value = prov;
  el.aiSendBtn.disabled = !(key && state.activeUsername);
}

function saveAiKey() {
  const key = el.aiKeyInput.value.trim();
  const prov = el.aiProvider.value;
  if (key) {
    localStorage.setItem(AI_KEY_STORAGE, key);
    localStorage.setItem(AI_PROV_STORAGE, prov);
    el.aiKeySave.textContent = "已保存 ✓";
    setTimeout(() => { el.aiKeySave.textContent = "保存"; }, 1500);
  } else {
    localStorage.removeItem(AI_KEY_STORAGE);
    el.aiKeySave.textContent = "已清除";
    setTimeout(() => { el.aiKeySave.textContent = "保存"; }, 1500);
  }
  el.aiSendBtn.disabled = !(key && state.activeUsername);
}

function refreshAiContactTitle() {
  const contact = state.contacts.find((c) => c.username === state.activeUsername);
  const name = contact?.display_name || state.activeUsername;
  const hasKey = !!localStorage.getItem(AI_KEY_STORAGE);
  const ready = !!(state.activeUsername && hasKey);
  if (state.activeUsername) {
    el.aiContactTitle.textContent = `关于「${name}」`;
    el.aiSendBtn.disabled = !hasKey;
  } else {
    el.aiContactTitle.textContent = "选择一个联系人开始分析";
    el.aiSendBtn.disabled = true;
  }
  if (el.aiReportBtn) el.aiReportBtn.disabled = !ready;
}

function appendAiMessage(role, text, isError = false) {
  const existing = el.aiThread.querySelector(".ai-empty");
  if (existing) existing.remove();
  const div = document.createElement("div");
  div.className = `ai-msg ai-msg-${role}${isError ? " ai-msg-error" : ""}`;
  div.innerHTML = `<div class="ai-bubble">${escapeHtml(text).replace(/\n/g, "<br>")}</div>`;
  el.aiThread.appendChild(div);
  el.aiThread.scrollTop = el.aiThread.scrollHeight;
}

async function sendAiQuery(event) {
  event.preventDefault();
  const question = el.aiInput.value.trim();
  if (!question || !state.activeUsername) return;
  const apiKey = localStorage.getItem(AI_KEY_STORAGE) || "";
  if (!apiKey) { alert("请先填写并保存 API Key。"); return; }

  el.aiInput.value = "";
  el.aiSendBtn.disabled = true;
  appendAiMessage("user", question);
  const thinking = document.createElement("div");
  thinking.className = "ai-msg ai-msg-assistant";
  thinking.innerHTML = `<div class="ai-bubble ai-thinking">正在思考…</div>`;
  el.aiThread.appendChild(thinking);
  el.aiThread.scrollTop = el.aiThread.scrollHeight;

  try {
    const res = await fetch("/api/ai/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contact: state.activeUsername,
        question,
        api_key: apiKey,
        provider: el.aiProvider.value,
      }),
    });
    const data = await res.json();
    thinking.remove();
    if (data.success) {
      appendAiMessage("assistant", data.answer);
    } else {
      appendAiMessage("assistant", data.message || "请求失败，请检查 API Key 和网络。", true);
    }
  } catch (err) {
    thinking.remove();
    appendAiMessage("assistant", "网络错误：" + err.message, true);
  } finally {
    el.aiSendBtn.disabled = false;
  }
}

function selectReportCount(count) {
  state.aiReportCount = count;
  document.querySelectorAll(".ai-count-btn").forEach((btn) => {
    btn.classList.toggle("active", Number(btn.dataset.count) === count);
  });
}

function renderReportText(text) {
  return text
    .split("\n")
    .map((line) => {
      if (/^## (.+)/.test(line)) {
        return `<h4 class="ai-report-heading">${escapeHtml(line.slice(3))}</h4>`;
      }
      const escaped = escapeHtml(line).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
      return escaped ? `<p>${escaped}</p>` : "";
    })
    .join("");
}

async function generateAiReport() {
  if (!state.activeUsername) return;
  const apiKey = localStorage.getItem(AI_KEY_STORAGE) || "";
  if (!apiKey) { alert("请先填写并保存 API Key。"); return; }

  el.aiReportBtn.disabled = true;
  el.aiReportBtn.textContent = "生成中…";
  el.aiReportResult.hidden = false;
  el.aiReportResult.innerHTML = `<div class="ai-report-loading">正在读取对话并分析，通常需要 15-30 秒…</div>`;

  try {
    const res = await fetch("/api/ai/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contact: state.activeUsername,
        message_count: state.aiReportCount,
        api_key: apiKey,
        provider: el.aiProvider.value,
      }),
    });
    const data = await res.json();
    if (data.success) {
      el.aiReportResult.innerHTML =
        `<div class="ai-report-meta">基于 ${data.sent_count} 条消息 · ${data.contact}</div>` +
        renderReportText(data.report);
    } else {
      el.aiReportResult.innerHTML =
        `<div class="ai-report-error">${escapeHtml(data.message || "生成失败，请检查 API Key。")}</div>`;
    }
  } catch (err) {
    el.aiReportResult.innerHTML = `<div class="ai-report-error">网络错误：${escapeHtml(err.message)}</div>`;
  } finally {
    el.aiReportBtn.disabled = false;
    el.aiReportBtn.textContent = "重新生成";
  }
}

document.querySelectorAll(".ai-count-btn").forEach((btn) => {
  btn.addEventListener("click", () => selectReportCount(Number(btn.dataset.count)));
});
el.aiReportBtn.addEventListener("click", generateAiReport);
el.aiKeySave.addEventListener("click", saveAiKey);
el.aiKeyInput.addEventListener("keydown", (e) => { if (e.key === "Enter") saveAiKey(); });
el.aiForm.addEventListener("submit", sendAiQuery);

function renderDemoBanner() {
  const existing = document.getElementById("demoBanner");
  if (existing) return;
  const bar = document.createElement("div");
  bar.id = "demoBanner";
  bar.className = "demo-banner";
  bar.textContent = "演示模式 — 合成数据，非真实聊天记录";
  document.querySelector(".app").prepend(bar);
}

async function loadSnapshotStatus() {
  try {
    const data = await api("/api/status");
    state.snapshotStatus = data;
    renderSnapshotStatus(data);
    if (data.demo_mode) renderDemoBanner();
    if (needsOnboarding(data) && state.activeView === "overview") {
      renderOnboarding(data);
    }
  } catch (_err) {
    el.snapshotBadge.textContent = "快照状态未知";
    el.snapshotBadge.classList.add("stale");
  }
}

async function refreshSnapshot() {
  const btn = el.snapshotRefreshBtn;
  btn.disabled = true;
  btn.classList.add("spinning");
  const prevText = el.snapshotBadge.textContent;
  el.snapshotBadge.textContent = "正在刷新快照…";
  el.snapshotBadge.classList.add("stale");

  try {
    const res = await fetch("/api/refresh", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      state.overviewLoaded = false;
      await loadSnapshotStatus();
      loadContacts().catch(() => {});
      if (state.activeView === "overview") loadOverview(true);
    } else {
      el.snapshotBadge.textContent = "刷新失败";
      el.snapshotBadge.title = data.message || "未知错误";
      el.snapshotBadge.classList.add("stale");
      if (state.activeView === "overview") {
        el.overviewContent.className = "overview-content";
        el.overviewContent.innerHTML = `
          <div class="refresh-error">
            <strong>快照刷新失败</strong>
            <p>${escapeHtml(data.message)}</p>
            ${data.error === "stale_keys" || data.error === "no_keys"
              ? `<p class="refresh-error-hint">需要重新运行密钥提取：<code>sudo python3 find_key_memscan.py</code></p>`
              : data.error === "no_sqlcipher"
              ? `<p class="refresh-error-hint">安装 sqlcipher：<code>brew install sqlcipher</code></p>`
              : ""}
          </div>`;
      }
    }
  } catch (_err) {
    el.snapshotBadge.textContent = prevText;
  } finally {
    btn.disabled = false;
    btn.classList.remove("spinning");
  }
}

const debouncedLoadContacts = debounce(loadContacts);

for (const button of el.navButtons) {
  button.addEventListener("click", () => switchView(button.dataset.view));
}
el.memoryForm.addEventListener("submit", (event) => {
  event.preventDefault();
  searchMemory();
});
el.searchBtn.addEventListener("click", loadContacts);
el.contactSearch.addEventListener("input", debouncedLoadContacts);
el.contactSearch.addEventListener("keydown", (event) => {
  if (event.key === "Enter") loadContacts();
});
el.refreshBtn.addEventListener("click", loadContacts);
el.overviewRefreshBtn.addEventListener("click", () => loadOverview(true));
el.overviewYear.addEventListener("change", () => loadOverview(true));
el.limitSelect.addEventListener("change", () => loadContact(state.activeUsername));
el.startDate.addEventListener("change", () => loadContact(state.activeUsername));
el.endDate.addEventListener("change", () => loadContact(state.activeUsername));
el.privacyRefreshBtn.addEventListener("click", loadPrivacy);
el.reportExportBtn.addEventListener("click", exportReport);
el.snapshotRefreshBtn.addEventListener("click", refreshSnapshot);

setupYearOptions();
loadAiKey();
const initialView = location.hash.replace("#", "") || "overview";
if (["overview", "chat", "memory", "report", "ai", "privacy", "roadmap"].includes(initialView)) switchView(initialView, false);

loadSnapshotStatus();
loadPrivacy();
loadContacts().catch((err) => {
  setStatus("加载失败");
  el.messages.className = "messages empty";
  el.messages.innerHTML = `<span>${escapeHtml(err.message)}</span>`;
});
