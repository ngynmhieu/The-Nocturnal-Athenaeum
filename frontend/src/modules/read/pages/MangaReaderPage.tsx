import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { ArrowLeft, Pencil, Check, Images, Link } from "lucide-react";
import { LoadingDialog } from "@/shared/ui";
import owlMascot from "@/shared/assets/owl_reading_book_with_glasses.png";
import { useSignedUrls, PoolPickerModal } from "../shared";
import { useSectionPages, useMangaDetail, sectionLabel } from "../entities";
import { useDeletePage, useReorderPages, useReaderWidth, usePageVersions, READER_WIDTHS } from "../features";
import type { Page } from "../entities";
import { Reader, PullPagesModal } from "../widgets";

/** /lector/manga/:mangaId/read/:sectionId — the reading view. View mode just
 *  reads; edit mode reveals the two ways to add pages: "Pull from link" (direct
 *  pull — a volume/chapter link's pages land here in the site's own order, see
 *  `PullPagesModal`) and "Add pages" (pick from the pool, for images collected
 *  earlier — see `PoolPickerModal`), plus per-page controls in the reader:
 *  remove a page, move it up / down one place, or add pages in front of /
 *  behind it (the pool picker again, with an insert position), upscale it or
 *  translate it by reference (preview → Accept / Discard), or remove a version. */
export function MangaReaderPage() {
  const { mangaId, sectionId } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  // One-shot seed (not kept in sync with the URL) — lets a freshly created,
  // empty section land straight in edit mode instead of a second click.
  const [editing, setEditing] = useState(() => searchParams.get("edit") === "1");
  // The pool picker is open when this isn't null: `"end"` appends (header's
  // "Add pages"), a number inserts at that position (a page's add before/after).
  const [poolAt, setPoolAt] = useState<number | "end" | null>(null);
  const [pullOpen, setPullOpen] = useState(false);
  // The header slides away while scrolling down through pages and returns on
  // scroll-up; it stays put in edit mode, where its buttons are the point.
  const [headerHidden, setHeaderHidden] = useState(false);
  const { pages, error, refresh } = useSectionPages(sectionId);
  const { deletePage, deletingId } = useDeletePage();
  const [pageError, setPageError] = useState<string | null>(null);
  const { width: readerWidth, setWidth: setReaderWidth } = useReaderWidth();

  // Upscale / translate-by-reference previews and accepted versions; every
  // change refetches the pages so the reader shows (and the menu offers) the
  // current versions.
  const versions = usePageVersions(refresh);

  const removePage = async (page: { id: string; position: number }) => {
    setPageError(null);
    // Removing the page under an open preview discards that preview first, so
    // its Storage file doesn't outlive the page.
    if (versions.preview?.pageId === page.id) await versions.discard();
    try {
      await deletePage(page.id);
    } catch {
      setPageError(`Couldn't remove page ${page.position + 1} — try again.`);
    }
    refresh();
  };
  // Move = swap with the neighbour, saved as a whole new order (the backend
  // rewrites every position in one transaction), then refetch.
  const { reorder } = useReorderPages(sectionId ?? "");
  const [movingId, setMovingId] = useState<string | null>(null);
  const movePage = async (page: Page, direction: -1 | 1) => {
    if (!pages || movingId) return;
    const from = pages.findIndex((p) => p.id === page.id);
    const to = from + direction;
    if (from < 0 || to < 0 || to >= pages.length) return;
    const ids = pages.map((p) => p.id);
    [ids[from], ids[to]] = [ids[to], ids[from]];
    setPageError(null);
    setMovingId(page.id);
    try {
      await reorder(ids);
    } catch {
      setPageError(`Couldn't move page ${page.position + 1} — try again.`);
    }
    await refresh();
    setMovingId(null);
  };
  const urls = useSignedUrls(
    (pages ?? []).flatMap((p) => [p.storagePath, ...(p.versions ?? []).map((v) => v.storagePath)])
  );
  // Non-blocking — the reader itself doesn't need the manga fetched, only its
  // title/section label for the header, so it fills in a beat after pages do.
  const { detail } = useMangaDetail(mangaId);
  const section = detail?.sections.find((s) => s.id === sectionId);
  // Back lands on the tab this section lives in (the sections page reads ?tab=).
  const backTab = section ? `?tab=${section.kind === "volume" ? "volumes" : "chapters"}` : "";

  if (error) {
    return <p className="py-12 text-center text-sm text-[var(--owl-brown-muted)]">{error}</p>;
  }
  if (pages === null) {
    return <LoadingDialog fullScreen={false} message="Fetching this section…" />;
  }

  return (
    <div className="flex flex-col md:h-full">
      {/* Folds to zero height (grid-rows 1fr → 0fr) rather than overlaying the
          pages, so the header keeps its transparent look on the app background. */}
      <div
        className={`grid shrink-0 transition-[grid-template-rows] duration-300 ${
          headerHidden && !editing ? "grid-rows-[0fr]" : "grid-rows-[1fr]"
        }`}
      >
        <div className="min-h-0 overflow-hidden">
          <header className="border-b border-[var(--owl-border)] px-6 py-4">
            <div className="mx-auto w-full max-w-5xl flex items-center gap-3">
              <button
                onClick={() => navigate(mangaId ? `/lector/manga/${mangaId}${backTab}` : "/lector")}
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
                {(pageError ?? versions.error) && (
                  <p className="text-sm text-[var(--owl-brown-deep)]">{pageError ?? versions.error}</p>
                )}
              </div>
              {/* Page-strip width — remembered per browser; phones always read full width. */}
              <div
                role="radiogroup"
                aria-label="Reader width"
                className="hidden md:flex items-center rounded-md border border-[var(--owl-border)] p-0.5"
              >
                {READER_WIDTHS.map((option) => (
                  <button
                    key={option.value}
                    role="radio"
                    aria-checked={readerWidth === option.value}
                    onClick={() => setReaderWidth(option.value)}
                    className={`rounded px-2.5 py-1 text-sm transition-colors cursor-pointer ${
                      readerWidth === option.value
                        ? "bg-[var(--owl-brown-mid)]/15 text-[var(--owl-brown-deep)]"
                        : "text-[var(--owl-brown-muted)] hover:bg-[var(--owl-brown-mid)]/10 hover:text-[var(--owl-brown-deep)]"
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
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
                  onClick={() => setPoolAt("end")}
                  className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer"
                >
                  <Images size={15} aria-hidden="true" />
                  Add pages
                </button>
              )}
              <button
                onClick={() => {
                  // Leaving edit mode drops the open preview, any preview still
                  // being generated, and the version error (the reader also
                  // ends pick-reference mode on its own).
                  if (editing) versions.dismiss();
                  setEditing((e) => !e);
                }}
                className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer"
              >
                {editing ? <Check size={15} aria-hidden="true" /> : <Pencil size={15} aria-hidden="true" />}
                {editing ? "Done" : "Edit"}
              </button>
            </div>
          </header>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        {pages.length === 0 ? (
          !editing && (
            <div className="flex flex-col items-center gap-3 py-12">
              <img src={owlMascot} alt="" aria-hidden="true" className="w-28 opacity-80" />
              <p className="text-sm text-[var(--owl-brown-muted)]">No pages yet — switch to Edit to add some.</p>
            </div>
          )
        ) : (
          <Reader
            pages={pages}
            urls={urls}
            width={readerWidth}
            onHeaderHiddenChange={setHeaderHidden}
            editing={editing}
            busyPageId={deletingId ?? movingId ?? versions.busyId}
            onRemovePage={removePage}
            onMovePage={movePage}
            onAddPagesAt={setPoolAt}
            onUpscalePage={(page) => {
              setPageError(null);
              void versions.upscale(page);
            }}
            onTranslatePage={(target, reference) => {
              setPageError(null);
              void versions.translate(target, reference);
            }}
            onRemoveVersion={(page, kind) => {
              setPageError(null);
              void versions.remove(page, kind);
            }}
            preview={versions.preview}
            versionsBusy={versions.busyId !== null}
            onAcceptPreview={() => void versions.accept()}
            onDiscardPreview={() => void versions.discard()}
          />
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
          open={poolAt !== null}
          onClose={() => setPoolAt(null)}
          target={{
            kind: "section-pages",
            sectionId,
            at: typeof poolAt === "number" ? poolAt : undefined,
            onDone: () => {
              setPoolAt(null);
              refresh();
            },
          }}
        />
      )}
    </div>
  );
}
