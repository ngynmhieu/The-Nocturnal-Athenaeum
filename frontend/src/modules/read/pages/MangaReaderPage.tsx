import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { ArrowLeft, Pencil, Check, Images, Link } from "lucide-react";
import { LoadingDialog } from "@/shared/ui";
import owlMascot from "@/shared/assets/owl_reading_book_with_glasses.png";
import { useSignedUrls, PoolPickerModal } from "../shared";
import { useSectionPages, useMangaDetail, sectionLabel } from "../entities";
import { Reader, PullPagesModal } from "../widgets";

/** /lector/manga/:mangaId/read/:sectionId — the reading view. View mode just
 *  reads; edit mode reveals the two ways to add pages: "Pull from link" (direct
 *  pull — a volume/chapter link's pages land here in the site's own order, see
 *  `PullPagesModal`) and "Add pages" (pick from the pool, for images collected
 *  earlier — see `PoolPickerModal`). */
export function MangaReaderPage() {
  const { mangaId, sectionId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // One-shot seed (not kept in sync with the URL) — lets a freshly created,
  // empty section land straight in edit mode instead of a second click.
  const [editing, setEditing] = useState(() => searchParams.get("edit") === "1");
  const [poolOpen, setPoolOpen] = useState(false);
  const [pullOpen, setPullOpen] = useState(false);
  const { pages, error, refresh } = useSectionPages(sectionId);
  const urls = useSignedUrls((pages ?? []).map((p) => p.storagePath));
  // Non-blocking — the reader itself doesn't need the manga fetched, only its
  // title/section label for the header, so it fills in a beat after pages do.
  const { detail } = useMangaDetail(mangaId);
  const section = detail?.sections.find((s) => s.id === sectionId);

  if (error) {
    return <p className="py-12 text-center text-sm text-[var(--owl-brown-muted)]">{error}</p>;
  }
  if (pages === null) {
    return <LoadingDialog fullScreen={false} message="Fetching this section…" />;
  }

  return (
    <div className="flex h-full flex-col">
      <header className="shrink-0 border-b border-[var(--owl-border)] px-6 py-4">
        <div className="mx-auto w-full max-w-5xl flex items-center gap-3">
          <button
            onClick={() => navigate(mangaId ? `/lector/manga/${mangaId}` : "/lector")}
            aria-label="Back to manga"
            className="p-1.5 rounded-md text-[var(--owl-brown-muted)] transition-colors hover:bg-[var(--owl-brown-mid)]/10 hover:text-[var(--owl-brown-deep)] cursor-pointer"
          >
            <ArrowLeft size={24} />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl text-[var(--owl-brown-dark)] truncate">
              {section ? sectionLabel(section) : "Reading"}
            </h1>
            <p className="text-sm text-[var(--owl-brown-muted)] truncate">
              {pages.length} page{pages.length === 1 ? "" : "s"}
            </p>
          </div>
          {editing && (
            <button
              onClick={() => setPullOpen(true)}
              className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer"
            >
              <Link size={15} aria-hidden="true" />
              Pull from link
            </button>
          )}
          {editing && (
            <button
              onClick={() => setPoolOpen(true)}
              className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer"
            >
              <Images size={15} aria-hidden="true" />
              Add pages
            </button>
          )}
          <button
            onClick={() => setEditing((e) => !e)}
            className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer"
          >
            {editing ? <Check size={15} aria-hidden="true" /> : <Pencil size={15} aria-hidden="true" />}
            {editing ? "Done" : "Edit"}
          </button>
        </div>
      </header>

      <div className="flex-1 min-h-0">
        {pages.length === 0 ? (
          !editing && (
            <div className="flex flex-col items-center gap-3 py-12">
              <img src={owlMascot} alt="" aria-hidden="true" className="w-28 opacity-80" />
              <p className="text-sm text-[var(--owl-brown-muted)]">No pages yet — switch to Edit to add some.</p>
            </div>
          )
        ) : (
          <Reader pages={pages} urls={urls} />
        )}
      </div>

      {sectionId && (
        <PullPagesModal
          open={pullOpen}
          onClose={() => setPullOpen(false)}
          sectionId={sectionId}
          onPulled={() => {
            setPullOpen(false);
            refresh();
          }}
        />
      )}

      {sectionId && (
        <PoolPickerModal
          open={poolOpen}
          onClose={() => setPoolOpen(false)}
          target={{
            kind: "section-pages",
            sectionId,
            onDone: () => {
              setPoolOpen(false);
              refresh();
            },
          }}
        />
      )}
    </div>
  );
}
