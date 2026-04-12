const state = {
  lang: "en",
  report: null,
  filteredItems: [],
  selectedIndex: -1,
};

const i18n = {
  en: {
    title: "Report Viewer",
    subtitle: "Offline JSON visualization for SignalRank AI reports.",
    upload: "Load JSON Report",
    overview: "Overview",
    filters: "Filters",
    results: "Results",
    details: "Details",
    empty: "Load a local JSON report to inspect scores, decisions, and AI overrides.",
    noResults: "No items match the current filters.",
    keepStatus: "Keep Status",
    channel: "Relevance Channel",
    significance: "Significance Type",
    aiRefined: "AI Refined",
    source: "Source",
    all: "All",
    kept: "Kept",
    dropped: "Dropped",
    yes: "Yes",
    no: "No",
    generatedAt: "Generated At",
    fetched: "Fetched",
    deduped: "Deduped",
    keptCount: "Kept",
    discarded: "Discarded",
    refinementMode: "Refinement Mode",
    aiRefinedCount: "AI Refined Count",
    sourceFailed: "Source Failed Count",
    aiOverrideCount: "AI Override Count",
    degradedCount: "Degraded Count",
    reportMeta: "Resume focus",
    keepReason: "Keep Reason",
    decisionSource: "Decision Source",
    keepReasonCategory: "Keep Reason Category",
    relevanceChannel: "Relevance Channel",
    significanceType: "Significance Type",
    summary: "Summary",
    scores: "Scores",
    localScores: "Local Scores",
    metadata: "Metadata",
    matchedTerms: "Matched Resume Terms",
    tags: "Tags",
    url: "URL",
    published: "Published",
    aiRefinedLabel: "AI Refined / Override",
    duplicateCount: "Duplicate Count",
    clusterSize: "Topic Cluster Size",
    heavyTechnical: "Technical Ecosystem Heavyweight",
    heavyCorporate: "Corporate or Consumer Heavyweight",
    industryHeavyweight: "Industry Heavyweight",
    finalScore: "Final",
    embeddingScore: "Embedding",
    localDiscovery: "Local Discovery",
    runTitle: "Run Pipeline",
    runHint: "Run the backend pipeline directly from the page, or load an existing JSON report below.",
    run: "Run",
    running: "Running...",
    runDone: "Run completed.",
    runFailed: "Run failed",
    resumeFile: "Resume File",
    sourcesPreset: "Sources Preset",
    sourcesFile: "Sources File",
    sourcesPresetCurated: "精选公开源",
    sourcesPresetExample: "最小示例源",
    sourcesPresetPremium: "Premium 占位源",
    aiEvaluateField: "AI Evaluate",
    aiExpandResume: "AI Expand Resume",
    generationApi: "Generation API",
    aiModelField: "AI Model",
    embeddingModelField: "Embedding Model",
    chatBaseUrl: "Chat Base URL",
    embeddingBaseUrl: "Embedding Base URL",
    chatApiKey: "Chat API Key",
    embeddingApiKey: "Embedding API Key",
    perSourceLimit: "Per Source Limit",
    topN: "Top N",
    chatTimeout: "Chat Timeout",
    embeddingTimeout: "Embedding Timeout",
    sourcesHelp: "If you upload a sources file, it overrides the preset. Curated is the recommended default.",
    basicSettingsTitle: "Basic Inputs",
    basicSettingsHelp: "Resume plus source configuration.",
    runScopeTitle: "Run Scope",
    runScopeHelp: "Control breadth and whether AI is enabled.",
    aiSettingsTitle: "AI Settings",
    aiSettingsHelp: "Only needed when AI Evaluate is enabled. Official OpenAI API keys work too.",
    localOnlyHint: "AI is disabled. Model, base URL, key, and timeout fields are hidden.",
  },
  zh: {
    title: "结果查看页",
    subtitle: "离线查看 SignalRank AI JSON 报告，重点看解释、分数和 AI 覆盖关系。",
    upload: "加载 JSON 报告",
    overview: "概览",
    filters: "过滤器",
    results: "结果列表",
    details: "详情",
    empty: "请先加载本地 JSON 报告，再查看结果、分数和 AI override。",
    noResults: "当前过滤条件下没有结果。",
    keepStatus: "保留状态",
    channel: "相关性通道",
    significance: "重要性类型",
    aiRefined: "AI 精修",
    source: "信源",
    all: "全部",
    kept: "保留",
    dropped: "丢弃",
    yes: "是",
    no: "否",
    generatedAt: "生成时间",
    fetched: "抓取数",
    deduped: "去重后",
    keptCount: "保留数",
    discarded: "丢弃数",
    refinementMode: "Refinement 模式",
    aiRefinedCount: "AI 精修条数",
    sourceFailed: "信源失败数",
    aiOverrideCount: "AI 覆盖数",
    degradedCount: "降级计数",
    reportMeta: "简历摘要",
    keepReason: "保留原因",
    decisionSource: "决策来源",
    keepReasonCategory: "保留类别",
    relevanceChannel: "相关性通道",
    significanceType: "重要性类型",
    summary: "摘要",
    scores: "最终分数",
    localScores: "本地分数",
    metadata: "元信息",
    matchedTerms: "命中的简历词",
    tags: "标签",
    url: "链接",
    published: "发布时间",
    aiRefinedLabel: "AI 精修 / 覆盖",
    duplicateCount: "重复计数",
    clusterSize: "主题聚类大小",
    heavyTechnical: "技术生态级重磅",
    heavyCorporate: "企业/消费级重磅",
    industryHeavyweight: "行业重磅",
    finalScore: "最终分",
    embeddingScore: "Embedding 分",
    localDiscovery: "本地 discovery",
    runTitle: "运行任务",
    runHint: "可直接从页面触发后端运行，也可以继续使用下方 JSON 离线查看。",
    run: "开始运行",
    running: "运行中...",
    runDone: "运行完成。",
    runFailed: "运行失败",
    resumeFile: "简历文件",
    sourcesPreset: "信源预设",
    sourcesFile: "信源文件",
    sourcesPresetCurated: "精选公开源",
    sourcesPresetExample: "最小示例源",
    sourcesPresetPremium: "Premium 占位源",
    aiEvaluateField: "是否启用 AI",
    aiExpandResume: "AI 扩展简历画像",
    generationApi: "生成接口",
    aiModelField: "AI 模型",
    embeddingModelField: "Embedding 模型",
    chatBaseUrl: "Chat Base URL",
    embeddingBaseUrl: "Embedding Base URL",
    chatApiKey: "Chat API Key",
    embeddingApiKey: "Embedding API Key",
    perSourceLimit: "每源条数",
    topN: "输出条数",
    chatTimeout: "Chat 超时",
    embeddingTimeout: "Embedding 超时",
    sourcesHelp: "如果上传了信源文件，将优先使用该文件并覆盖信源预设。默认推荐“精选公开源”。",
    basicSettingsTitle: "基础输入",
    basicSettingsHelp: "先选择简历和信源配置。",
    runScopeTitle: "运行范围",
    runScopeHelp: "控制抓取规模，以及是否启用 AI。",
    aiSettingsTitle: "AI 参数",
    aiSettingsHelp: "只有启用 AI 时才需要填写。官方 OpenAI API key 也可以直接使用。AI 扩展画像失败时会自动回退到本地扩展。",
    localOnlyHint: "当前未启用 AI，模型、地址、密钥和超时参数已隐藏。",
  },
};

const els = {
  fileInput: document.getElementById("file-input"),
  langToggle: document.getElementById("lang-toggle"),
  overviewGrid: document.getElementById("overview-grid"),
  resultsList: document.getElementById("results-list"),
  detailEmpty: document.getElementById("detail-empty"),
  detailView: document.getElementById("detail-view"),
  resultsCount: document.getElementById("results-count"),
  reportMeta: document.getElementById("report-meta"),
  filterKeep: document.getElementById("filter-keep"),
  filterChannel: document.getElementById("filter-channel"),
  filterSignificance: document.getElementById("filter-significance"),
  filterAi: document.getElementById("filter-ai"),
  filterSource: document.getElementById("filter-source"),
  runForm: document.getElementById("run-form"),
  runButton: document.getElementById("run-button"),
  runStatus: document.getElementById("run-status"),
  aiEvaluate: document.getElementById("ai-evaluate"),
  aiSettings: document.getElementById("ai-settings"),
  sourcesHelp: document.getElementById("sources-help"),
  sourcesPreset: document.getElementById("sources-preset"),
};

function t(key) {
  return i18n[state.lang][key] || key;
}

function init() {
  bindEvents();
  updateStaticCopy();
  syncRunFormState();
  setEmptyState();
}

function bindEvents() {
  els.fileInput.addEventListener("change", onFileChange);
  els.runButton.addEventListener("click", onRunPipeline);
  els.aiEvaluate.addEventListener("change", syncRunFormState);
  els.langToggle.addEventListener("click", () => {
    state.lang = state.lang === "en" ? "zh" : "en";
    updateStaticCopy();
    render();
  });
  [els.filterKeep, els.filterChannel, els.filterSignificance, els.filterAi, els.filterSource].forEach((node) => {
    node.addEventListener("change", applyFilters);
  });
}

function updateStaticCopy() {
  document.getElementById("page-title").textContent = t("title");
  document.getElementById("page-subtitle").textContent = t("subtitle");
  document.getElementById("upload-label").textContent = t("upload");
  document.getElementById("overview-title").textContent = t("overview");
  document.getElementById("run-title").textContent = t("runTitle");
  document.getElementById("run-meta").textContent = t("runHint");
  document.getElementById("filters-title").textContent = t("filters");
  document.getElementById("results-title").textContent = t("results");
  document.getElementById("detail-title").textContent = t("details");
  document.getElementById("filter-keep-label").textContent = t("keepStatus");
  document.getElementById("filter-channel-label").textContent = t("channel");
  document.getElementById("filter-significance-label").textContent = t("significance");
  document.getElementById("filter-ai-label").textContent = t("aiRefined");
  document.getElementById("filter-source-label").textContent = t("source");
  document.getElementById("resume-file-label").textContent = t("resumeFile");
  document.getElementById("sources-preset-label").textContent = t("sourcesPreset");
  document.getElementById("sources-file-label").textContent = t("sourcesFile");
  document.getElementById("basic-settings-title").textContent = t("basicSettingsTitle");
  document.getElementById("basic-settings-help").textContent = t("basicSettingsHelp");
  document.getElementById("run-scope-title").textContent = t("runScopeTitle");
  document.getElementById("run-scope-help").textContent = t("runScopeHelp");
  document.getElementById("ai-expand-resume-label").textContent = t("aiExpandResume");
  document.getElementById("ai-evaluate-label").textContent = t("aiEvaluateField");
  document.getElementById("generation-api-label").textContent = t("generationApi");
  document.getElementById("ai-model-label").textContent = t("aiModelField");
  document.getElementById("embedding-model-label").textContent = t("embeddingModelField");
  document.getElementById("chat-base-url-label").textContent = t("chatBaseUrl");
  document.getElementById("embedding-base-url-label").textContent = t("embeddingBaseUrl");
  document.getElementById("chat-api-key-label").textContent = t("chatApiKey");
  document.getElementById("embedding-api-key-label").textContent = t("embeddingApiKey");
  document.getElementById("per-source-limit-label").textContent = t("perSourceLimit");
  document.getElementById("top-n-label").textContent = t("topN");
  document.getElementById("chat-timeout-label").textContent = t("chatTimeout");
  document.getElementById("embedding-timeout-label").textContent = t("embeddingTimeout");
  document.getElementById("ai-settings-title").textContent = t("aiSettingsTitle");
  document.getElementById("ai-settings-help").textContent = t("aiSettingsHelp");
  els.sourcesHelp.textContent = t("sourcesHelp");
  els.runButton.textContent = t("run");
  els.langToggle.textContent = state.lang === "en" ? "中文" : "EN";
  updatePresetLabels();
  syncRunFormState();
}

function syncRunFormState() {
  const aiEnabled = els.aiEvaluate.value === "true";
  els.aiSettings.classList.toggle("hidden", !aiEnabled);
  if (aiEnabled) {
    els.runStatus.textContent = "";
  } else {
    els.runStatus.textContent = t("localOnlyHint");
  }
}

function updatePresetLabels() {
  const labels = {
    curated: t("sourcesPresetCurated"),
    example: t("sourcesPresetExample"),
    premium: t("sourcesPresetPremium"),
  };
  [...els.sourcesPreset.options].forEach((option) => {
    option.textContent = labels[option.value] || option.value;
  });
}

async function onRunPipeline() {
  const resumeFile = document.getElementById("resume-file").files?.[0];
  if (!resumeFile) {
    els.runStatus.textContent = `${t("runFailed")}: missing resume file`;
    return;
  }
  const formData = new FormData(els.runForm);
  els.runButton.disabled = true;
  els.runStatus.textContent = t("running");
  try {
    const response = await fetch("/api/run", {
      method: "POST",
      body: formData,
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      throw new Error(payload.detail || payload.error || "Request failed");
    }
    state.report = payload.report;
    buildFilters();
    applyFilters();
    els.runStatus.textContent = `${t("runDone")} JSON: ${payload.saved_files?.json || "-"}`;
  } catch (error) {
    els.runStatus.textContent = `${t("runFailed")}: ${error}`;
  } finally {
    els.runButton.disabled = false;
  }
}

function onFileChange(event) {
  const [file] = event.target.files || [];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    try {
      state.report = JSON.parse(String(reader.result));
      buildFilters();
      applyFilters();
    } catch (error) {
      alert(`Invalid JSON: ${error}`);
    }
  };
  reader.readAsText(file);
}

function buildFilters() {
  const items = state.report?.items || [];
  populateSelect(els.filterKeep, [
    ["all", t("all")],
    ["keep", t("kept")],
    ["discard", t("dropped")],
  ]);
  populateSelect(els.filterAi, [
    ["all", t("all")],
    ["true", t("yes")],
    ["false", t("no")],
  ]);
  populateSelect(els.filterChannel, [["all", t("all")], ...uniqueOptions(items.map((item) => item.relevance_channel))]);
  populateSelect(els.filterSignificance, [["all", t("all")], ...uniqueOptions(items.map((item) => item.significance_type))]);
  populateSelect(els.filterSource, [["all", t("all")], ...uniqueOptions(items.map((item) => item.source_name))]);
}

function populateSelect(selectNode, options) {
  selectNode.innerHTML = options
    .map(([value, label]) => `<option value="${escapeHtml(value)}">${escapeHtml(label)}</option>`)
    .join("");
}

function uniqueOptions(values) {
  return [...new Set(values.filter(Boolean))].sort().map((value) => [value, value]);
}

function applyFilters() {
  const items = state.report?.items || [];
  state.filteredItems = items.filter((item) => {
    if (els.filterKeep.value === "keep" && !item.keep) return false;
    if (els.filterKeep.value === "discard" && item.keep) return false;
    if (els.filterChannel.value !== "all" && item.relevance_channel !== els.filterChannel.value) return false;
    if (els.filterSignificance.value !== "all" && item.significance_type !== els.filterSignificance.value) return false;
    if (els.filterAi.value !== "all" && String(item.ai_refined) !== els.filterAi.value) return false;
    if (els.filterSource.value !== "all" && item.source_name !== els.filterSource.value) return false;
    return true;
  });
  state.selectedIndex = state.filteredItems.length > 0 ? 0 : -1;
  render();
}

function render() {
  renderOverview();
  renderList();
  renderDetail();
}

function renderOverview() {
  if (!state.report) {
    els.overviewGrid.innerHTML = "";
    els.reportMeta.textContent = "";
    return;
  }
  const stats = state.report.stats || {};
  const metrics = [
    [t("generatedAt"), state.report.generated_at || "-"],
    [t("fetched"), stats.fetched_count ?? "-"],
    [t("deduped"), stats.deduped_count ?? "-"],
    [t("keptCount"), stats.kept_count ?? "-"],
    [t("discarded"), stats.discarded_count ?? "-"],
    [t("refinementMode"), stats.refinement_mode ?? "-"],
    [t("aiRefinedCount"), stats.ai_refined_count ?? "-"],
    [t("aiOverrideCount"), stats.ai_override_count ?? "-"],
    [t("degradedCount"), stats.degraded_count ?? "-"],
    [t("sourceFailed"), stats.source_failed_count ?? "-"],
  ];
  els.overviewGrid.innerHTML = metrics
    .map(
      ([label, value]) => `
        <article class="metric-card">
          <div class="metric-label">${escapeHtml(String(label))}</div>
          <div class="metric-value ${metricValueClass(label, value)}">${escapeHtml(formatMetricValue(label, value))}</div>
        </article>
      `
    )
    .join("");
  els.reportMeta.textContent = `${t("reportMeta")}: ${state.report.resume_focus || "-"}`;
}

function renderList() {
  if (!state.report) {
    els.resultsCount.textContent = "";
    els.resultsList.innerHTML = "";
    return;
  }
  els.resultsCount.textContent = `${state.filteredItems.length} / ${state.report.items.length}`;
  if (state.filteredItems.length === 0) {
    els.resultsList.innerHTML = `<p class="empty-state">${escapeHtml(t("noResults"))}</p>`;
    return;
  }
  els.resultsList.innerHTML = state.filteredItems
    .map((item, index) => {
      const activeClass = index === state.selectedIndex ? "active" : "";
      return `
        <article class="result-card ${activeClass}" data-index="${index}">
          <h3>${escapeHtml(item.title)}</h3>
          <div class="result-meta">
            <span>${escapeHtml(item.source_name || "-")}</span>
            <span>${escapeHtml(item.published || "-")}</span>
          </div>
          <div class="chip-row">
            <span class="chip ${item.keep ? "keep" : "drop"}">${item.keep ? t("kept") : t("dropped")}</span>
            <span class="chip">${escapeHtml(item.relevance_channel || "-")}</span>
            <span class="chip">${escapeHtml(item.significance_type || "-")}</span>
            <span class="chip">${escapeHtml(item.decision_source || "-")}</span>
          </div>
          <div class="result-scores">
            <span>${t("finalScore")}: ${escapeHtml(String(item.scores?.final ?? "-"))}</span>
            <span>${t("embeddingScore")}: ${escapeHtml(String(item.embedding_score ?? "-"))}</span>
            <span>${t("localDiscovery")}: ${escapeHtml(String(item.local_scores?.discovery ?? "-"))}</span>
          </div>
        </article>
      `;
    })
    .join("");
  document.querySelectorAll(".result-card").forEach((node) => {
    node.addEventListener("click", () => {
      state.selectedIndex = Number(node.dataset.index);
      renderList();
      renderDetail();
    });
  });
}

function renderDetail() {
  if (!state.report || state.selectedIndex < 0 || !state.filteredItems[state.selectedIndex]) {
    setEmptyState();
    return;
  }
  const item = state.filteredItems[state.selectedIndex];
  els.detailEmpty.classList.add("hidden");
  els.detailView.classList.remove("hidden");
  els.detailView.innerHTML = `
    <h3>${escapeHtml(item.title)}</h3>
    <p class="detail-meta">${escapeHtml(item.source_name || "-")} · ${escapeHtml(item.published || "-")}</p>

    <section class="detail-section">
      <div class="detail-grid">
        ${detailCard(t("keepReason"), item.keep_reason)}
        ${detailCard(t("decisionSource"), item.decision_source)}
        ${detailCard(t("keepReasonCategory"), item.keep_reason_category)}
        ${detailCard(t("relevanceChannel"), item.relevance_channel)}
        ${detailCard(t("significanceType"), item.significance_type)}
        ${detailCard(t("aiRefinedLabel"), `${item.ai_refined} / ${item.ai_override}`)}
      </div>
    </section>

    <section class="detail-section">
      <h4>${t("summary")}</h4>
      <p class="detail-summary">${escapeHtml(item.summary || "-")}</p>
    </section>

    <section class="detail-section">
      <h4>${t("scores")}</h4>
      <div class="detail-grid">
        ${scoreCards(item.scores)}
      </div>
    </section>

    <section class="detail-section">
      <h4>${t("localScores")}</h4>
      <div class="detail-grid">
        ${scoreCards(item.local_scores)}
      </div>
    </section>

    <section class="detail-section">
      <h4>${t("metadata")}</h4>
      <div class="detail-grid">
        ${detailCard(t("published"), item.published || "-")}
        ${detailCard(t("matchedTerms"), (item.matched_resume_terms || []).join(", ") || "-")}
        ${detailCard(t("tags"), (item.tags || []).join(", ") || "-")}
        ${detailCard(t("url"), item.url || "-")}
        ${detailCard(t("duplicateCount"), item.duplicate_count)}
        ${detailCard(t("clusterSize"), item.topic_cluster_size)}
        ${detailCard(t("industryHeavyweight"), item.industry_heavyweight)}
        ${detailCard(t("heavyTechnical"), item.technical_ecosystem_heavyweight)}
        ${detailCard(t("heavyCorporate"), item.corporate_or_consumer_heavyweight)}
      </div>
    </section>
  `;
}

function detailCard(label, value) {
  const normalized = value ?? "-";
  const rendered = renderDetailValue(label, normalized);
  return `
    <article class="detail-card">
      <strong>${escapeHtml(String(label))}</strong>
      ${rendered}
    </article>
  `;
}

function scoreCards(scores = {}) {
  return Object.entries(scores)
    .map(([key, value]) => detailCard(key, value))
    .join("");
}

function setEmptyState() {
  els.detailEmpty.classList.remove("hidden");
  els.detailView.classList.add("hidden");
  els.detailEmpty.textContent = t("empty");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function metricValueClass(label, value) {
  const normalized = String(value ?? "");
  if (label === t("generatedAt") || normalized.length > 20) {
    return "compact";
  }
  return "";
}

function formatMetricValue(label, value) {
  if (label === t("generatedAt")) {
    return formatDateTime(value);
  }
  return String(value ?? "-");
}

function renderDetailValue(label, value) {
  const normalized = String(value ?? "-");
  if (label === t("url") && normalized !== "-") {
    const href = escapeHtml(normalized);
    return `<a class="mono url" href="${href}" target="_blank" rel="noreferrer">${href}</a>`;
  }
  if (label === t("published")) {
    return `<span class="mono">${escapeHtml(formatDateTime(normalized))}</span>`;
  }
  if (normalized.length > 32 || normalized.includes("://")) {
    return `<span class="mono">${escapeHtml(normalized)}</span>`;
  }
  return `<span>${escapeHtml(normalized)}</span>`;
}

function formatDateTime(value) {
  const raw = String(value ?? "-");
  if (!raw || raw === "-") return "-";
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleString(state.lang === "zh" ? "zh-CN" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

init();
