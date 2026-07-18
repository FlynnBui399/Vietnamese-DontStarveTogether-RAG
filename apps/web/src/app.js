import { renderRagPage } from "./components.js";
import { ragData } from "./data.js";

const root = document.querySelector("#app");

if (!(root instanceof HTMLElement)) {
  throw new Error("The RAG application root is missing");
}

const state = {
  activeRoute: "ask",
  activePageTab: "ask",
  drawerOpen: false,
  collapsedSections: new Set(),
  draft: "",
  lastQuestion: "",
  loading: false,
  result: null,
  error: "",
  statusMessage: "",
  health: {
    status: "checking",
    detail: "Đang kết nối tới API...",
    llm: "",
    embedding: "",
    vector_store: "",
  },
};

let statusTimer;

function render() {
  root.innerHTML = renderRagPage(ragData, state);
  document.body.classList.toggle("drawer-open", state.drawerOpen);
}

function announce(message) {
  state.statusMessage = message;
  render();
  window.clearTimeout(statusTimer);
  statusTimer = window.setTimeout(() => {
    state.statusMessage = "";
    const region = document.querySelector("#status-region");
    if (region) {
      region.textContent = "";
      region.classList.remove("is-visible");
    }
  }, 3200);
}

function focusAfterRender(selector) {
  window.requestAnimationFrame(() => document.querySelector(selector)?.focus());
}

function scrollAfterRender(selector) {
  window.requestAnimationFrame(() => document.querySelector(selector)?.scrollIntoView({ behavior: "smooth", block: "start" }));
}

function errorMessage(payload, status) {
  if (status === 429) return "Bạn đang gửi câu hỏi quá nhanh. Hãy chờ một chút rồi thử lại.";
  if (typeof payload?.detail === "string") return payload.detail;
  if (status === 503) return "API chưa được cấu hình đầy đủ. Hãy kiểm tra Supabase và LLM provider.";
  return "Không thể kết nối tới dịch vụ RAG. Hãy kiểm tra API và thử lại.";
}

async function checkHealth() {
  try {
    const response = await fetch("/api/health", { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("Health endpoint unavailable");
    const payload = await response.json();
    const ready = payload.status === "ready";
    state.health = {
      status: ready ? "ready" : "not-ready",
      detail: ready ? "API và các provider đã được cấu hình." : "API đang chạy nhưng provider chưa được cấu hình đủ.",
      llm: payload.llm ?? "",
      embedding: payload.embedding ?? "",
      vector_store: payload.vector_store ?? "",
    };
  } catch {
    state.health = {
      status: "not-ready",
      detail: "Không kết nối được /api/health.",
      llm: "",
      embedding: "",
      vector_store: "",
    };
  }
  render();
}

async function askQuestion(question) {
  const message = question.trim();
  if (!message || state.loading) return;

  state.draft = message;
  state.lastQuestion = message;
  state.loading = true;
  state.error = "";
  state.result = null;
  state.activePageTab = "ask";
  state.activeRoute = "answer";
  render();
  scrollAfterRender("#answer");

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ message }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(errorMessage(payload, response.status));
    if (typeof payload.answer !== "string" || !Array.isArray(payload.sources)) {
      throw new Error("API trả về dữ liệu không đúng contract answer + sources.");
    }
    state.result = { answer: payload.answer, sources: payload.sources };
    state.draft = "";
    state.activeRoute = "answer";
  } catch (error) {
    state.error = error instanceof Error ? error.message : "Đã xảy ra lỗi không xác định.";
  } finally {
    state.loading = false;
    render();
    scrollAfterRender("#answer");
  }
}

function navigate(route) {
  state.activeRoute = route;
  state.drawerOpen = false;

  if (route === "pipeline" || route === "auto-ingest") {
    state.activePageTab = "pipeline";
    render();
    scrollAfterRender(route === "auto-ingest" ? "#auto-ingest" : "#pipeline");
    return;
  }

  if (["ask", "answer", "sources"].includes(route)) {
    state.activePageTab = "ask";
    render();
    scrollAfterRender(route === "ask" ? "#rag-question" : `#${route}`);
    if (route === "ask") focusAfterRender("#rag-question");
    return;
  }

  render();
  scrollAfterRender(`#${route}`);
}

function handleAction(trigger) {
  const action = trigger.dataset.action;

  if (action === "toggle-drawer") {
    state.drawerOpen = !state.drawerOpen;
    render();
    if (state.drawerOpen) focusAfterRender(".left-sidebar__mobile-title button");
    return;
  }

  if (action === "close-drawer") {
    state.drawerOpen = false;
    render();
    focusAfterRender(".mobile-menu-button");
    return;
  }

  if (action === "toggle-sidebar-section") {
    const section = trigger.dataset.section;
    if (state.collapsedSections.has(section)) state.collapsedSections.delete(section);
    else state.collapsedSections.add(section);
    render();
    return;
  }

  if (action === "navigate") {
    navigate(trigger.dataset.route ?? "ask");
    return;
  }

  if (action === "set-page-tab") {
    state.activePageTab = trigger.dataset.value === "pipeline" ? "pipeline" : "ask";
    state.activeRoute = state.activePageTab;
    render();
    scrollAfterRender("#main-content");
    return;
  }

  if (action === "ask-suggestion") {
    askQuestion(trigger.dataset.question ?? "");
    return;
  }

  if (action === "retry-question") {
    askQuestion(state.lastQuestion);
  }
}

root.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) return;
  const trigger = event.target.closest("[data-action]");
  if (!(trigger instanceof HTMLElement)) return;
  event.preventDefault();
  handleAction(trigger);
});

root.addEventListener("input", (event) => {
  if (event.target instanceof HTMLTextAreaElement && event.target.matches("#rag-question")) {
    state.draft = event.target.value;
  }
});

root.addEventListener("submit", (event) => {
  if (!(event.target instanceof HTMLFormElement) || !event.target.matches("[data-chat-form]")) return;
  event.preventDefault();
  const formData = new FormData(event.target);
  const message = String(formData.get("message") ?? "");
  if (!message.trim()) {
    announce("Hãy nhập một câu hỏi trước khi gửi.");
    focusAfterRender("#rag-question");
    return;
  }
  askQuestion(message);
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.drawerOpen) {
    state.drawerOpen = false;
    render();
    focusAfterRender(".mobile-menu-button");
  }

  if ((event.ctrlKey || event.metaKey) && event.key === "Enter" && event.target instanceof HTMLTextAreaElement) {
    event.preventDefault();
    event.target.form?.requestSubmit();
  }
});

render();
checkHealth();
