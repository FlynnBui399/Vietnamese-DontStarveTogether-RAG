const escapeHtml = (value = "") =>
  String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

function safeUrl(value = "") {
  try {
    const url = new URL(String(value), window.location.origin);
    return ["http:", "https:"].includes(url.protocol) ? escapeHtml(url.href) : "#";
  } catch {
    return "#";
  }
}

function brandRune() {
  return `
    <svg viewBox="0 0 72 72" aria-hidden="true">
      <path d="M36 6 45 23 64 26 50 40 55 61 36 51 17 62 22 41 7 27 27 23Z" fill="#d8ceb6" stroke="#17100c" stroke-width="5"/>
      <path d="M36 17v35M23 30l27 14M49 29 23 45" fill="none" stroke="#4b3427" stroke-width="4" stroke-linecap="round"/>
      <circle cx="36" cy="35" r="6" fill="#17100c"/>
    </svg>`;
}

function WikiLogo() {
  return `
    <a class="wiki-logo" href="#ask" data-action="navigate" data-route="ask" aria-label="DST RAG Field Guide — trang hỏi đáp">
      <span class="wiki-logo__rune">${brandRune()}</span>
      <span class="wiki-logo__text">
        <span class="wiki-logo__kicker">Vietnamese knowledge assistant</span>
        <span class="wiki-logo__title">Chatbot for Don't Starve Together (Đừng chết đói)</span>
        <span class="wiki-logo__subtitle">Wiki-grounded survival answers</span>
      </span>
    </a>`;
}

function HealthBadge({ health }) {
  const label = health.status === "ready" ? "RAG sẵn sàng" : health.status === "checking" ? "Đang kiểm tra" : "Chưa sẵn sàng";
  return `
    <button class="health-badge health-badge--${escapeHtml(health.status)}" type="button" data-action="navigate" data-route="system-status">
      <span aria-hidden="true"></span>${label}
    </button>`;
}

function WikiHeader({ state }) {
  return `
    <header class="wiki-header">
      <div class="wiki-header__scratches" aria-hidden="true"></div>
      <div class="wiki-header__inner">
        <button class="mobile-menu-button" type="button" data-action="toggle-drawer" aria-controls="left-sidebar" aria-expanded="${state.drawerOpen}">
          <span></span><span></span><span></span><span class="sr-only">Mở mục lục</span>
        </button>
        ${WikiLogo()}
        <div class="wiki-header__tools">
          
          ${HealthBadge({ health: state.health })}
        </div>
      </div>
    </header>`;
}

function SidebarLink({ link, activeRoute }) {
  const external = Boolean(link.href);
  const href = external ? link.href : `#${link.route}`;
  const action = external ? "" : `data-action="navigate" data-route="${escapeHtml(link.route)}"`;
  const active = !external && activeRoute === link.route;
  return `
    <li>
      <a class="sidebar-link${active ? " is-active" : ""}" href="${escapeHtml(href)}" ${action} ${active ? 'aria-current="page"' : ""}>
        <span aria-hidden="true">${escapeHtml(link.icon)}</span><span>${escapeHtml(link.label)}</span>${external ? '<small aria-hidden="true">↗</small>' : ""}
      </a>
    </li>`;
}

function SidebarSection({ section, state }) {
  const collapsed = state.collapsedSections.has(section.id);
  return `
    <section class="sidebar-section rough-frame rough-frame--small">
      <button class="sidebar-section__title" type="button" data-action="toggle-sidebar-section" data-section="${escapeHtml(section.id)}" aria-expanded="${!collapsed}">
        <span>${escapeHtml(section.title)}</span><span aria-hidden="true">${collapsed ? "+" : "−"}</span>
      </button>
      <ul class="sidebar-section__links" ${collapsed ? "hidden" : ""}>
        ${section.links.map((link) => SidebarLink({ link, activeRoute: state.activeRoute })).join("")}
      </ul>
    </section>`;
}

function LeftSidebar({ sections, state }) {
  return `
    <aside id="left-sidebar" class="left-sidebar${state.drawerOpen ? " is-open" : ""}" aria-label="Mục lục RAG">
      <div class="left-sidebar__mobile-title"><span>Field Index</span><button type="button" data-action="close-drawer" aria-label="Đóng mục lục">×</button></div>
      ${sections.map((section) => SidebarSection({ section, state })).join("")}
    </aside>
    <button class="drawer-scrim${state.drawerOpen ? " is-visible" : ""}" type="button" data-action="close-drawer" aria-label="Đóng mục lục"></button>`;
}

function PageTabs({ tabs, active }) {
  return `
    <nav class="page-tabs" aria-label="Chế độ hiển thị">
      ${tabs.map((tab) => `<button type="button" class="page-tab${active === tab.id ? " is-active" : ""}" data-action="set-page-tab" data-value="${tab.id}" ${active === tab.id ? 'aria-current="page"' : ""}>${escapeHtml(tab.label)}</button>`).join("")}
    </nav>`;
}

function WelcomePanel() {
  return `
    <section class="welcome-panel rough-frame" aria-labelledby="welcome-title">
      <div class="welcome-panel__mark" aria-hidden="true">?</div>
      <div>
        <p class="eyebrow">Tàng Thư DST</p>
        <h1 id="welcome-title">Hỏi về <em>Don't Starve Together</em></h1>
        <p>Hỏi xoáy đáp xoay với tựa game DST dùng tiếng Việt. Giúp các bạn có thể dễ hiểu hơn và có src đầy đủ</p>
      </div>
      <div class="welcome-panel__seal"><strong>RAG</strong><span>evidence first</span></div>
    </section>`;
}

function SuggestedQuestions({ questions }) {
  return `
    <div class="suggestions">
      <p><span aria-hidden="true">✦</span> Có thể bạn muốn hỏi</p>
      <div class="suggestions__grid">
        ${questions.map((item) => `<button type="button" data-action="ask-suggestion" data-question="${escapeHtml(item.question)}"><small>${escapeHtml(item.label)}</small><span>${escapeHtml(item.question)}</span><b aria-hidden="true">↗</b></button>`).join("")}
      </div>
    </div>`;
}

function AskComposer({ state }) {
  return `
    <form class="ask-composer rough-frame" data-chat-form>
      <label for="rag-question"><span>Hãy hỏi để chơi game dễ hơn nhé!</span><small>Tối đa 1.000 ký tự</small></label>
      <div class="ask-composer__field">
        <textarea id="rag-question" name="message" maxlength="1000" rows="3" placeholder="Ví dụ: Football Helmet có tác dụng gì?" ${state.loading ? "disabled" : ""}>${escapeHtml(state.draft)}</textarea>
        <button type="submit" ${state.loading ? "disabled" : ""}>
          <span aria-hidden="true">${state.loading ? "⌛" : "✦"}</span>${state.loading ? "Đang truy xuất..." : "Gửi câu hỏi"}
        </button>
      </div>
      <div class="ask-composer__meta"><span><i aria-hidden="true"></i> Wiki-grounded</span><span>Câu trả lời tiếng Việt</span><span>Trích dẫn [Sx]</span></div>
    </form>`;
}

function formatAnswer(answer, sourceCount) {
  const safe = escapeHtml(answer).replaceAll("\n", "<br>");
  return safe.replace(/\[S(\d+)\]/g, (match, number) => {
    const index = Number(number);
    return index > 0 && index <= sourceCount ? `<a class="citation-mark" href="#source-${index}">${match}</a>` : match;
  });
}

function SourceCard({ source, index }) {
  return `
    <a id="source-${index}" class="source-card" href="${safeUrl(source.url)}" target="_blank" rel="noreferrer">
      <span class="source-card__index">S${index}</span>
      <span class="source-card__copy"><strong>${escapeHtml(source.title)}</strong><small>${escapeHtml(source.section || "Trang Wiki")}</small></span>
      <span aria-hidden="true">↗</span>
    </a>`;
}

function AnswerPanel({ state }) {
  if (state.loading) {
    return `
      <section id="answer" class="answer-panel answer-panel--loading rough-frame" aria-live="polite">
        <div class="retrieval-loader" aria-hidden="true"><span></span><span></span><span></span></div>
        <div><p class="eyebrow">Retrieval in progress</p><h2>Đang lần theo dấu vết trong Wiki...</h2><p>Hệ thống đang embedding câu hỏi, tìm evidence và chuẩn bị câu trả lời có nguồn.</p></div>
      </section>`;
  }

  if (state.error) {
    return `
      <section id="answer" class="answer-panel answer-panel--error rough-frame" role="alert">
        <div class="answer-panel__icon" aria-hidden="true">!</div><div><p class="eyebrow">Không thể hoàn tất truy vấn</p><h2>RAG service chưa trả lời</h2><p>${escapeHtml(state.error)}</p><button type="button" data-action="retry-question">Thử lại câu hỏi</button></div>
      </section>`;
  }

  if (!state.result) {
    return `
      <section id="answer" class="answer-empty rough-frame" aria-labelledby="answer-empty-title">
        <div class="answer-empty__art" aria-hidden="true"><span>?</span></div>
        <div><p class="eyebrow">Answer workspace</p><h2 id="answer-empty-title">Câu trả lời sẽ xuất hiện tại đây</h2><p>Chọn một gợi ý hoặc đặt câu hỏi riêng. Trợ lý sẽ hiển thị nội dung trả lời cùng danh sách nguồn Wiki đã dùng.</p></div>
      </section>`;
  }

  return `
    <section id="answer" class="answer-panel rough-frame" aria-live="polite">
      <header class="answer-panel__header">
        <div><p class="eyebrow">Grounded response</p><h2>${escapeHtml(state.lastQuestion)}</h2></div>
        <span class="evidence-badge">${state.result.sources.length} nguồn</span>
      </header>
      <div class="answer-panel__body"><span class="answer-panel__icon" aria-hidden="true">✦</span><p>${formatAnswer(state.result.answer, state.result.sources.length)}</p></div>
      <div id="sources" class="sources-section">
        ${state.result.sources.length ? `<div class="sources-grid">${state.result.sources.map((source, index) => SourceCard({ source, index: index + 1 })).join("")}</div>` : '<p class="sources-empty">Response không chứa nguồn tham chiếu.</p>'}
      </div>
    </section>`;
}

function PipelineStrip({ steps }) {
  return `
    <section class="pipeline-strip" aria-labelledby="pipeline-strip-title">
      <div class="section-heading"><div><p class="eyebrow">Traceable by design</p><h2 id="pipeline-strip-title">Một câu hỏi đi qua hệ thống thế nào?</h2></div><button type="button" data-action="set-page-tab" data-value="pipeline">Xem chi tiết →</button></div>
      <ol>${steps.map((step) => `<li><span>${escapeHtml(step.icon)}</span><small>${escapeHtml(step.index)}</small><strong>${escapeHtml(step.shortTitle)}</strong></li>`).join("")}</ol>
    </section>`;
}

function AskView({ data, state }) {
  return `${WelcomePanel()}${AskComposer({ state })}${SuggestedQuestions({ questions: data.suggestedQuestions })}${AnswerPanel({ state })}${PipelineStrip({ steps: data.pipelineSteps })}`;
}

function PipelineView({ data }) {
  return `
    <section id="pipeline" class="pipeline-view">
      <div class="pipeline-view__intro rough-frame"><p class="eyebrow">System map</p><h1>Từ câu hỏi đến câu trả lời có căn cứ</h1><p>Pipeline: <strong>Wiki → bge-m3 → Supabase pgvector → LLM → answer + sources.</strong></p></div>
      <ol class="pipeline-list">${data.pipelineSteps.map((step) => `<li class="pipeline-card rough-frame"><span class="pipeline-card__number">${escapeHtml(step.index)}</span><span class="pipeline-card__icon" aria-hidden="true">${escapeHtml(step.icon)}</span><div><small>${escapeHtml(step.title)}</small><h2>${escapeHtml(step.shortTitle)}</h2><p>${escapeHtml(step.description)}</p></div></li>`).join("")}</ol>
      <section id="auto-ingest" class="auto-ingest-card rough-frame"><div aria-hidden="true">↻</div><div><p class="eyebrow">On-demand knowledge</p><h2>Auto-ingest khi kho tri thức chưa có dữ liệu</h2><p>Retrieval rỗng không đồng nghĩa với đoán câu trả lời. Hệ thống sẽ tìm trang Wiki liên quan, chia nhỏ và embedding nội dung, lưu vào Supabase rồi thử truy xuất thêm một lần.</p></div></section>
    </section>`;
}

function SystemStatus({ state }) {
  const rows = [
    ["LLM provider", state.health.llm || "—"],
    ["Embedding", state.health.embedding || "—"],
    ["Vector store", state.health.vector_store || "Supabase"],
  ];
  return `
    <section id="system-status" class="widget-panel rough-frame">
      <div class="widget-panel__title"><span aria-hidden="true">⌁</span><h2>System status</h2></div>
      <div class="widget-panel__body">
        <div class="system-state system-state--${escapeHtml(state.health.status)}"><i aria-hidden="true"></i><div><strong>${state.health.status === "ready" ? "RAG service ready" : state.health.status === "checking" ? "Checking service" : "Service not ready"}</strong><span>${escapeHtml(state.health.detail)}</span></div></div>
        <dl class="system-facts">${rows.map(([term, value]) => `<div><dt>${term}</dt><dd>${escapeHtml(value)}</dd></div>`).join("")}</dl>
      </div>
    </section>`;
}

function RightSidebar({ data, state }) {
  return `
    <aside class="right-sidebar" aria-label="Thông tin hệ thống">
      ${SystemStatus({ state })}
      <section id="knowledge" class="widget-panel rough-frame"><div class="widget-panel__title"><span aria-hidden="true">▤</span><h2>Evidence policy</h2></div><div class="widget-panel__body"><ul class="rule-list">${data.sourceRules.map((rule) => `<li><span aria-hidden="true">✓</span>${escapeHtml(rule)}</li>`).join("")}</ul></div></section>
      <aside class="field-note rough-frame"><span>FIELD NOTE 07</span><p>Tên vật phẩm và nhân vật có thể viết bằng tiếng Anh; câu trả lời vẫn được tổng hợp bằng tiếng Việt.</p></aside>
    </aside>`;
}

function MainContent({ data, state }) {
  return `
    <main id="main-content" class="content-shell rough-frame" tabindex="-1">
      <div class="content-shell__tabs">${PageTabs({ tabs: data.pageTabs, active: state.activePageTab })}<span class="content-shell__edition"></span></div>
      <div class="content-shell__body">${state.activePageTab === "pipeline" ? PipelineView({ data }) : AskView({ data, state })}</div>
    </main>`;
}

function WikiFooter() {
  return `<footer class="wiki-footer"><div class="wiki-footer__rune">${brandRune()}</div><div><strong>DST RAG Field Guide</strong><p>Vietnamese RAG assistant grounded in Don't Starve Together Wiki evidence.</p></div><nav><a href="/docs">API docs</a><a href="#pipeline" data-action="set-page-tab" data-value="pipeline">RAG pipeline</a></nav></footer>`;
}

export function renderRagPage(data, state) {
  return `
    <a class="skip-link" href="#main-content">Đi tới nội dung chính</a>
    ${WikiHeader({ state })}
    <div class="wiki-layout">${LeftSidebar({ sections: data.navigationSections, state })}${MainContent({ data, state })}${RightSidebar({ data, state })}</div>
    ${WikiFooter()}
    <div id="status-region" class="status-toast${state.statusMessage ? " is-visible" : ""}" role="status" aria-live="polite">${escapeHtml(state.statusMessage)}</div>`;
}
