import { useState } from "react";
import { Globe, Upload, X } from "lucide-react";
import { Modal, Tabs, Tooltip } from "@/shared/ui";
import { usePoolAssets, type LibraryAsset, type Page } from "../../entities";
import {
  useInsertFromLibrary,
  useCollectToLibrary,
  useSetMangaCover,
  useSetSectionCover,
} from "../../features";
import { useSignedUrls } from "../useSignedUrls";
import { useClickSelect } from "../useClickSelect";
import { PickerGrid } from "./PickerGrid";
import { ScrapePicker } from "./ScrapePicker";
import { UploadTray } from "./UploadTray";

/** What picking from the pool is for — one pool, three destinations. Only
 *  `section-pages` allows more than one pick (a cover is always exactly one).
 *  `section-pages` with `at` inserts from that position instead of appending. */
export type PoolPickerTarget =
  | { kind: "section-pages"; sectionId: string; at?: number; onDone: (pages: Page[]) => void }
  | { kind: "manga-cover"; mangaId: string; onDone: () => void }
  | { kind: "section-cover"; sectionId: string; onDone: () => void };

interface PoolPickerModalProps {
  open: boolean;
  onClose: () => void;
  target: PoolPickerTarget;
}

type CollectMode = "scrape" | "upload";

const COLLECT_MODE_TABS: { value: CollectMode; label: string; icon: typeof Globe }[] = [
  { value: "scrape", label: "Scrape", icon: Globe },
  { value: "upload", label: "Upload", icon: Upload },
];

/** How loose images reach a section or a cover: collect into the pool
 *  (scrape or upload — identical to LibraryPage's "Collect images"), then pick
 *  from that same grid. Merging the collect step into this "window" keeps one
 *  collect path for pages and covers alike. (The exception is a whole volume/
 *  chapter from a supported site: the direct pull — `PullPagesModal` /
 *  `PullSeriesModal` — skips the pool and keeps the site's page order.) */
export function PoolPickerModal({ open, onClose, target }: PoolPickerModalProps) {
  const [mode, setMode] = useState<CollectMode>("scrape");
  const { assets, loading, appendAsset, removeAssets } = usePoolAssets();
  const urls = useSignedUrls(assets.map((a) => a.storagePath));
  const { picked, setPicked, onItemClick: multiItemClick } = useClickSelect(assets.map((a) => a.id));
  const { importUrlsToLibrary, uploadFilesToLibrary, collecting, importStatus } = useCollectToLibrary();

  // Rules of hooks: all three targets' hooks are called every render, each
  // holding a harmless id when its target kind isn't the active one — only
  // the one matching `target.kind` in `confirm` below ever actually fires.
  const { insert, inserting, insertStatus } = useInsertFromLibrary(
    target.kind === "section-pages" ? target.sectionId : ""
  );
  const { setCover: setMangaCover, setting: settingMangaCover } = useSetMangaCover(
    target.kind === "manga-cover" ? target.mangaId : ""
  );
  const { setCover: setSectionCover, setting: settingSectionCover } = useSetSectionCover(
    target.kind === "section-cover" ? target.sectionId : ""
  );

  const singleSelect = target.kind !== "section-pages";
  const onItemClick = singleSelect
    ? (key: string) => setPicked((prev) => (prev[0] === key ? [] : [key]))
    : multiItemClick;

  const busy = target.kind === "section-pages" ? inserting : target.kind === "manga-cover" ? settingMangaCover : settingSectionCover;
  const heading =
    target.kind !== "section-pages"
      ? "Choose a cover from the pool"
      : target.at === undefined
        ? "Add pages from the pool"
        : `Add pages from the pool — they'll go in as page ${target.at + 1}`;
  const confirmLabel = target.kind === "section-pages" ? "Add" : "Use as cover";
  const busyLabel = target.kind === "section-pages" ? "Adding…" : "Setting…";

  const confirm = async () => {
    if (target.kind === "section-pages") {
      const pages = await insert(picked, target.at);
      removeAssets(picked);
      setPicked([]);
      target.onDone(pages);
      return;
    }
    const assetId = picked[0];
    if (!assetId) return;
    if (target.kind === "manga-cover") {
      await setMangaCover(assetId);
    } else {
      await setSectionCover(assetId);
    }
    removeAssets([assetId]);
    setPicked([]);
    target.onDone();
  };

  const label = (asset: LibraryAsset) => asset.sourceUrl ?? undefined;

  return (
    <Modal open={open} onClose={onClose} size="window">
      <div className="flex items-center gap-2">
        <h2 className="flex-1 text-base font-medium text-[var(--owl-brown-dark)]">{heading}</h2>
        <Tooltip content="Close" side="right">
          <button
            onClick={onClose}
            aria-label="Close"
            className="p-1.5 rounded-md text-[var(--owl-brown-muted)] transition-colors hover:bg-[var(--owl-brown-mid)]/10 hover:text-[var(--owl-brown-deep)] cursor-pointer"
          >
            <X size={16} />
          </button>
        </Tooltip>
      </div>

      <section className="mt-3 rounded-md border border-[var(--owl-border)] bg-[var(--owl-cream)]/30 p-4 flex flex-col gap-3">
        <div className="flex items-center gap-2">
          <h3 className="flex-1 text-xs font-medium text-[var(--owl-brown-deep)]">Collect images</h3>
          <Tabs tabs={COLLECT_MODE_TABS} active={mode} onChange={setMode} />
        </div>
        {mode === "scrape" ? (
          <ScrapePicker
            busy={collecting}
            importStatus={importStatus}
            onImport={async (scrapedUrls, referer) => {
              await importUrlsToLibrary(scrapedUrls, referer, (_key, result) => {
                if (result.ok) appendAsset(result.asset);
              });
            }}
          />
        ) : (
          <UploadTray
            busy={collecting}
            uploadStatus={importStatus}
            onConfirm={async (items) => {
              await uploadFilesToLibrary(items, (_key, result) => {
                if (result.ok) appendAsset(result.asset);
              });
            }}
          />
        )}
      </section>

      <div className="mt-4">
        <h3 className="mb-2 text-xs font-medium text-[var(--owl-brown-deep)]">Your pool</h3>
        {loading ? (
          <p className="text-sm text-[var(--owl-brown-muted)]">Loading…</p>
        ) : assets.length === 0 ? (
          <p className="text-sm text-[var(--owl-brown-muted)]">Nothing in your pool yet — collect some above.</p>
        ) : (
          <PickerGrid
            items={assets.map((a) => ({ key: a.id, previewUrl: urls[a.storagePath] ?? "", label: label(a) }))}
            picked={picked}
            onItemClick={onItemClick}
            onSelectAll={() => setPicked(assets.map((a) => a.id))}
            onClear={() => setPicked([])}
            singleSelect={singleSelect}
            busy={busy}
            busyLabel={busyLabel}
            confirmLabel={confirmLabel}
            importStatus={target.kind === "section-pages" ? insertStatus : undefined}
            onConfirm={confirm}
          />
        )}
      </div>
    </Modal>
  );
}
