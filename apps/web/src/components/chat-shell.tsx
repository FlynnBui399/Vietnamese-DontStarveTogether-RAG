"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import { CitationCards } from "@/components/citation-cards";
import { CorpusStatus } from "@/components/corpus-status";
import { SafeAnswer } from "@/components/safe-answer";
import { SourceDrawer } from "@/components/source-drawer";
import type { ChatResponse, Citation, CorpusStatus as CorpusStatusData } from "@/lib/types";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";
const suggestions = [
  "Mũ da heo chế tạo như thế nào?",
  "Thermal Stone dùng để làm gì?",
  "So sánh Football Helmet và Log Suit",
  "Wendy có phù hợp cho người mới không?",
];

const confidenceLabels = {
  high: "Tin cậy cao",
  medium: "Tin cậy vừa",
  low: "Tin cậy thấp",
  none: "Không đủ bằng chứng",
};

type Exchange = {
  id: number;
  question: string;
  response: ChatResponse;
};

export function ChatShell() {
  const [query, setQuery] = useState("");
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [corpus, setCorpus] = useState<CorpusStatusData | null>(null);
  const [corpusLoading, setCorpusLoading] = useState(true);
  const [corpusFailed, setCorpusFailed] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    async function loadCorpusStatus() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/corpus/status`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("Corpus status unavailable");
        }
        setCorpus((await response.json()) as CorpusStatusData);
      } catch (reason) {
        if (!(reason instanceof DOMException && reason.name === "AbortError")) {
          setCorpusFailed(true);
        }
      } finally {
        setCorpusLoading(false);
      }
    }
    void loadCorpusStatus();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [exchanges, loading]);

  async function submitQuestion(question: string) {
    const message = question.trim();
    if (!message || loading) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, filters: { game_scope: "dst" } }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(payload?.detail ?? "Không thể nhận câu trả lời lúc này.");
      }
      const answer = (await response.json()) as ChatResponse;
      setExchanges((current) => [
        ...current,
        { id: Date.now(), question: message, response: answer },
      ]);
      setQuery("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Không thể kết nối tới trợ lý.");
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submitQuestion(query);
  }

  return (
    <div className="appShell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="DST Vietnamese Assistant - đầu trang">
          <span className="brandMark" aria-hidden="true">D</span>
          <span>
            <strong>DST Assistant</strong>
            <small>Hỏi đáp tiếng Việt có dẫn nguồn</small>
          </span>
        </a>
        <CorpusStatus status={corpus} loading={corpusLoading} failed={corpusFailed} />
      </header>

      <main className="chatMain" id="top">
        {exchanges.length === 0 ? (
          <section className="welcome" aria-labelledby="welcome-title">
            <p className="eyebrow">DON&apos;T STARVE TOGETHER · VIETNAMESE RAG</p>
            <h1 id="welcome-title">Hỏi game. Đọc đúng nguồn.</h1>
            <p className="welcomeCopy">
              Tra cứu vật phẩm, nhân vật, công thức và cơ chế bằng tiếng Việt — kể cả khi bạn
              không nhớ đúng tên tiếng Anh hoặc không gõ dấu.
            </p>
            <div className="suggestionGrid" aria-label="Câu hỏi gợi ý">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="suggestion"
                  onClick={() => void submitQuestion(suggestion)}
                  disabled={loading}
                >
                  <span>{suggestion}</span>
                  <span aria-hidden="true">↗</span>
                </button>
              ))}
            </div>
          </section>
        ) : (
          <section className="conversation" aria-label="Cuộc trò chuyện">
            {exchanges.map((exchange) => (
              <article className="exchange" key={exchange.id}>
                <div className="userMessage">
                  <span className="messageLabel">Bạn</span>
                  <p>{exchange.question}</p>
                </div>
                <div className={`assistantMessage ${exchange.response.abstained ? "abstained" : ""}`}>
                  <div className="answerHeader">
                    <span className="assistantAvatar" aria-hidden="true">D</span>
                    <div>
                      <span className="messageLabel">DST Assistant</span>
                      <span className={`confidence confidence-${exchange.response.confidence}`}>
                        {confidenceLabels[exchange.response.confidence]}
                      </span>
                    </div>
                  </div>

                  {exchange.response.resolved_entities.length > 0 ? (
                    <div className="resolvedAliases">
                      Đã hiểu: {exchange.response.resolved_entities.map((entity) => (
                        <span key={`${entity.entity_slug}-${entity.matched_alias}`}>
                          “{entity.matched_alias}” → <strong>{entity.entity_title}</strong>
                        </span>
                      ))}
                    </div>
                  ) : null}

                  {exchange.response.subjective_warning ? (
                    <p className="guideWarning">
                      Nội dung dưới đây có sử dụng nguồn hướng dẫn mang tính khuyến nghị.
                    </p>
                  ) : null}

                  {exchange.response.conflicts.length > 0 ? (
                    <div className="conflictWarning">
                      <strong>Nguồn có thông tin mâu thuẫn.</strong> Trợ lý giữ lại các giá trị để
                      bạn đối chiếu thay vì tự chọn một kết luận.
                    </div>
                  ) : null}

                  <SafeAnswer
                    answer={exchange.response.answer}
                    citations={exchange.response.citations}
                    onSelectCitation={setSelectedCitation}
                  />
                  <CitationCards
                    citations={exchange.response.citations}
                    onSelect={setSelectedCitation}
                  />
                  <p className="answerMeta">
                    Corpus {exchange.response.corpus_version ?? "—"} · {Math.round(exchange.response.latency_ms.total)} ms
                  </p>
                </div>
              </article>
            ))}
          </section>
        )}

        {loading ? (
          <div className="thinking" role="status" aria-live="polite">
            <span className="thinkingDot" />
            <span className="thinkingDot" />
            <span className="thinkingDot" />
            Đang tìm và kiểm tra nguồn…
          </div>
        ) : null}
        <div ref={endRef} />
      </main>

      <div className="composerDock">
        {error ? <div className="errorBanner" role="alert">{error}</div> : null}
        {!corpusLoading && !corpusFailed && !corpus?.available ? (
          <div className="errorBanner neutral" role="status">
            Cần kích hoạt một corpus hợp lệ trước khi đặt câu hỏi.
          </div>
        ) : null}
        <form className="composer" onSubmit={onSubmit}>
          <label className="srOnly" htmlFor="chat-query">Nhập câu hỏi về Don&apos;t Starve Together</label>
          <textarea
            id="chat-query"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void submitQuestion(query);
              }
            }}
            placeholder="Ví dụ: mu da heo chế như thế nào?"
            maxLength={2000}
            rows={1}
            disabled={loading}
          />
          <button className="sendButton" type="submit" disabled={loading || !query.trim()}>
            <span>Gửi</span><span aria-hidden="true">↑</span>
          </button>
        </form>
        <p className="composerNote">Câu trả lời chỉ dùng corpus DST đã lập chỉ mục và luôn kiểm tra citation.</p>
      </div>

      <SourceDrawer citation={selectedCitation} onClose={() => setSelectedCitation(null)} />
    </div>
  );
}
