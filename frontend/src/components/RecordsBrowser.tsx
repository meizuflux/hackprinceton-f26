import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { CaseData } from "../api/types";
import { EvidenceBrowser } from "./EvidenceBrowser";
import { useState } from "react";

const PAGE = 100;

/** Normalized ingestion records from the backend, filtered by evidence file and paged. */
export function RecordsBrowser({
  data,
  onInspect,
}: {
  data: CaseData;
  onInspect: (sourceId: string) => void;
}) {
  const [evidenceId, setEvidenceId] = useState("");
  const files = useQuery({
    queryKey: ["files", data.id],
    queryFn: () => api.listFiles(data.id),
  });
  const records = useInfiniteQuery({
    queryKey: ["records", data.id, evidenceId],
    queryFn: ({ pageParam }) =>
      api.getRecords(data.id, {
        evidenceId: evidenceId || undefined,
        limit: PAGE,
        offset: pageParam,
      }),
    initialPageParam: 0,
    getNextPageParam: (last) =>
      last.offset + last.items.length < last.total
        ? last.offset + last.items.length
        : undefined,
  });
  const items = records.data?.pages.flatMap((page) => page.items) ?? [];
  const total = records.data?.pages[0]?.total;
  const selectedFile = files.data?.find(
    (file) => file.evidenceId === evidenceId,
  );

  return (
    <EvidenceBrowser
      data={data}
      mode="generalized"
      generalizedRecords={items}
      recordTotal={total}
      onInspect={onInspect}
      recordFilter={
        files.data && files.data.length > 0 ? (
          <div className="records-filter">
            <label>
              Evidence file
              <select
                value={evidenceId}
                onChange={(event) => setEvidenceId(event.target.value)}
              >
                <option value="">All files ({files.data.length})</option>
                {files.data.map((file) => (
                  <option key={file.evidenceId} value={file.evidenceId}>
                    {file.evidenceId} · {file.filename} · {file.recordCount}{" "}
                    records
                  </option>
                ))}
              </select>
            </label>
            {selectedFile && (
              <p className="records-file-meta">
                {selectedFile.evidenceType} · {selectedFile.format} ·{" "}
                {selectedFile.parseStatus} ·{" "}
                {selectedFile.manifestMatch === true
                  ? "manifest hash matches"
                  : selectedFile.manifestMatch === false
                    ? "manifest hash MISMATCH"
                    : "no manifest hash"}{" "}
                · <code>{selectedFile.sha256}</code>
              </p>
            )}
          </div>
        ) : undefined
      }
      recordFooter={
        records.hasNextPage ? (
          <button
            type="button"
            className="button button-secondary records-more"
            disabled={records.isFetchingNextPage}
            onClick={() => void records.fetchNextPage()}
          >
            {records.isFetchingNextPage
              ? "Loading…"
              : `Load ${Math.min(PAGE, (total ?? 0) - items.length)} more`}
          </button>
        ) : undefined
      }
    />
  );
}
