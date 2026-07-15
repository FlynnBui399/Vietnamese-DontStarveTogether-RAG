"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  service: string;
  status: "ok" | "degraded";
  environment: string;
  supabase: {
    status: "connected" | "not_configured" | "unavailable";
    detail: string;
  };
};

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export function HealthStatus() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadHealth() {
      try {
        const response = await fetch(`${apiBaseUrl}/api/health`, {
          cache: "no-store",
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        setHealth((await response.json()) as HealthResponse);
      } catch (reason) {
        if (reason instanceof DOMException && reason.name === "AbortError") {
          return;
        }
        setError("Không thể kết nối tới FastAPI backend.");
      }
    }

    void loadHealth();
    return () => controller.abort();
  }, []);

  if (error) {
    return <div className="status statusError">{error}</div>;
  }

  if (!health) {
    return <div className="status">Đang kiểm tra backend…</div>;
  }

  return (
    <div className="statusGrid" aria-live="polite">
      <div className="status">
        <span>FastAPI</span>
        <strong className={health.status === "ok" ? "good" : "warn"}>{health.status}</strong>
      </div>
      <div className="status">
        <span>Supabase</span>
        <strong className={health.supabase.status === "connected" ? "good" : "warn"}>
          {health.supabase.status}
        </strong>
        <small>{health.supabase.detail}</small>
      </div>
    </div>
  );
}

