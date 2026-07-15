import type { Citation } from "@/lib/types";

type CitationCardsProps = {
  citations: Citation[];
  onSelect: (citation: Citation) => void;
};

export function CitationCards({ citations, onSelect }: CitationCardsProps) {
  if (citations.length === 0) {
    return null;
  }
  return (
    <section className="sourcesSection" aria-label="Nguồn trích dẫn">
      <h3>Nguồn đã kiểm chứng</h3>
      <div className="sourceCards">
        {citations.map((citation) => (
          <button
            className="sourceCard"
            key={citation.id}
            type="button"
            onClick={() => onSelect(citation)}
          >
            <span className="sourceId">{citation.id}</span>
            <span className="sourceTitle">{citation.page_title}</span>
            <span className="sourceSection">{citation.section}</span>
            <span className="sourceAction">Xem đoạn nguồn →</span>
          </button>
        ))}
      </div>
    </section>
  );
}
