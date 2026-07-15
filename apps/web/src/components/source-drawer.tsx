"use client";

import { useEffect, useRef } from "react";

import type { Citation } from "@/lib/types";

type SourceDrawerProps = {
  citation: Citation | null;
  onClose: () => void;
};

export function SourceDrawer({ citation, onClose }: SourceDrawerProps) {
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!citation) {
      return;
    }
    closeButton.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [citation, onClose]);

  if (!citation) {
    return null;
  }

  return (
    <div className="drawerLayer" role="presentation" onMouseDown={onClose}>
      <aside
        className="sourceDrawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-drawer-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="drawerHeader">
          <div>
            <p className="drawerEyebrow">Nguồn {citation.id}</p>
            <h2 id="source-drawer-title">{citation.page_title}</h2>
          </div>
          <button
            ref={closeButton}
            className="iconButton"
            type="button"
            onClick={onClose}
            aria-label="Đóng đoạn nguồn"
          >
            ×
          </button>
        </div>

        <dl className="sourceMetadata">
          <div>
            <dt>Section</dt>
            <dd>{citation.section}</dd>
          </div>
          <div>
            <dt>Revision</dt>
            <dd>{citation.revision_id}</dd>
          </div>
          <div>
            <dt>Corpus</dt>
            <dd>{citation.corpus_version}</dd>
          </div>
          <div>
            <dt>Loại nguồn</dt>
            <dd>{citation.source_kind}</dd>
          </div>
        </dl>

        {citation.subjective ? (
          <p className="drawerWarning">Đoạn này thuộc nội dung hướng dẫn có tính chủ quan.</p>
        ) : null}

        <div className="evidenceBlock">
          <p>{citation.content}</p>
        </div>

        <a className="wikiLink" href={citation.url} target="_blank" rel="noreferrer">
          Mở trang gốc trên Don&apos;t Starve Wiki
          <span aria-hidden="true">↗</span>
        </a>
        <p className="attribution">
          Nguồn: Don&apos;t Starve Wiki / wiki.gg. Nội dung văn bản có thể thuộc CC BY-SA 4.0.
        </p>
      </aside>
    </div>
  );
}
