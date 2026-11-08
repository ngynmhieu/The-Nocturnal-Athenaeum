import { useState } from "react";
import { Upload, Globe } from "lucide-react";
import { Tabs } from "@/shared/ui";
import { ScrapePicker, UploadTray } from "../../shared";
import { useCollectToLibrary } from "../../features";
import type { LibraryAsset } from "../../entities";

type CollectMode = "scrape" | "upload";

const COLLECT_MODE_TABS: { value: CollectMode; label: string; icon: typeof Globe }[] = [
  { value: "scrape", label: "Scrape", icon: Globe },
  { value: "upload", label: "Upload", icon: Upload },
];

interface LibraryCollectProps {
  /** Called the moment each item finishes collecting, one at a time. */
  onAssetCollected: (asset: LibraryAsset) => void;
}

/** Collect images into the pool — scrape a site or upload local files, the
 *  same two-tab flow `PoolPickerModal` reuses. Each item reveals in the pool
 *  the instant it finishes (see `useCollectToLibrary`), not batched to the end. */
export function LibraryCollect({ onAssetCollected }: LibraryCollectProps) {
  const [mode, setMode] = useState<CollectMode>("scrape");
  const { importUrlsToLibrary, uploadFilesToLibrary, collecting, importStatus } = useCollectToLibrary();

  return (
    <section className="rounded-md border border-[var(--owl-border)] bg-[var(--owl-cream)]/30 p-4 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="flex-1 text-xs font-medium text-[var(--owl-brown-deep)]">Collect images</h2>
        <Tabs tabs={COLLECT_MODE_TABS} active={mode} onChange={setMode} />
      </div>
      {mode === "scrape" ? (
        <ScrapePicker
          busy={collecting}
          importStatus={importStatus}
          onImport={async (urls, referer) => {
            await importUrlsToLibrary(urls, referer, (_key, result) => {
              if (result.ok) onAssetCollected(result.asset);
            });
          }}
        />
      ) : (
        <UploadTray
          busy={collecting}
          uploadStatus={importStatus}
          onConfirm={async (items) => {
            await uploadFilesToLibrary(items, (_key, result) => {
              if (result.ok) onAssetCollected(result.asset);
            });
          }}
        />
      )}
    </section>
  );
}
