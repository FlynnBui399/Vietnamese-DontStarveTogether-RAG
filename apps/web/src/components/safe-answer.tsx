import type { Citation } from "@/lib/types";

type SafeAnswerProps = {
  answer: string;
  citations: Citation[];
  onSelectCitation: (citation: Citation) => void;
};

const citationPattern = /(\[S[1-9][0-9]*\])/g;

export function SafeAnswer({ answer, citations, onSelectCitation }: SafeAnswerProps) {
  const citationMap = new Map(citations.map((citation) => [`[${citation.id}]`, citation]));
  const parts = answer.split(citationPattern);

  return (
    <div className="answerText">
      {parts.map((part, index) => {
        const citation = citationMap.get(part);
        if (!citation) {
          return <span key={`${index}-${part.slice(0, 8)}`}>{part}</span>;
        }
        return (
          <button
            className="inlineCitation"
            key={`${citation.id}-${index}`}
            type="button"
            onClick={() => onSelectCitation(citation)}
            aria-label={`Xem nguồn ${citation.id}: ${citation.page_title}`}
          >
            {citation.id}
          </button>
        );
      })}
    </div>
  );
}
