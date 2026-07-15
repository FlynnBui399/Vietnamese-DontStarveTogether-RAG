import { HealthStatus } from "@/components/health-status";

export default function Home() {
  return (
    <main>
      <section className="panel">
        <p className="eyebrow">Milestone 0</p>
        <h1>DST Vietnamese Knowledge Assistant</h1>
        <p className="intro">
          Nền tảng phát triển cho trợ lý hỏi đáp tiếng Việt có dẫn nguồn về Don&apos;t Starve
          Together.
        </p>
        <HealthStatus />
      </section>
    </main>
  );
}

