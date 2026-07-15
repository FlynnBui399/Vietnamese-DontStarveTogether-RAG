import type { CorpusStatus as CorpusStatusData } from "@/lib/types";

type CorpusStatusProps = {
  status: CorpusStatusData | null;
  loading: boolean;
  failed: boolean;
};

function compactNumber(value: number) {
  return new Intl.NumberFormat("vi-VN", { notation: "compact" }).format(value);
}

export function CorpusStatus({ status, loading, failed }: CorpusStatusProps) {
  if (loading) {
    return <div className="corpusPill corpusLoading">Đang kiểm tra corpus…</div>;
  }
  if (failed) {
    return <div className="corpusPill corpusOffline">Không đọc được trạng thái corpus</div>;
  }
  if (!status?.available) {
    return <div className="corpusPill corpusOffline">Chưa có corpus đang hoạt động</div>;
  }
  return (
    <div className="corpusPill" title={`Embedding: ${status.embedding_model ?? "—"}`}>
      <span className="statusDot" aria-hidden="true" />
      <span>Corpus {status.version}</span>
      <span className="corpusMeta">
        {compactNumber(status.page_count)} trang · {compactNumber(status.chunk_count)} đoạn
      </span>
    </div>
  );
}
