import { useState } from "react";
import { LoadingDialog } from "@/shared/ui";
import { usePoolAssets } from "../entities";
import { LibraryHeader, LibraryCollect, LibraryStorage } from "../widgets";

/** /lector/pool — manage the staging pool: collect images (scrape or upload)
 *  with no manga attached, or discard ones you don't want. Organizing them
 *  into a manga's volume/chapter happens from that section, not here. */
export function LibraryPage() {
  const { assets, loading, error, appendAsset, removeAssets } = usePoolAssets();

  /** View is read-only (click to preview); edit reveals selection + delete. */
  const [editing, setEditing] = useState(false);

  // Initial load — show only the mascot dialog, nothing else on the page yet.
  if (loading && assets.length === 0) {
    return <LoadingDialog fullScreen={false} message="Fetching your pool…" />;
  }

  return (
    <div className="md:h-full md:overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-6 py-6 flex flex-col gap-5">
        <LibraryHeader editing={editing} onToggleEditing={() => setEditing((e) => !e)} />
        <LibraryCollect onAssetCollected={appendAsset} />
        <LibraryStorage assets={assets} error={error} editing={editing} removeAssets={removeAssets} />
      </div>
    </div>
  );
}
