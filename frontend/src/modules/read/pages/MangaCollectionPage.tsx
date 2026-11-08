import { useState } from "react";
import { useNavigate } from "react-router";
import { Layers, Pencil, Check } from "lucide-react";
import { LoadingDialog } from "@/shared/ui";
import owlMascot from "@/shared/assets/owl_reading_book_with_glasses.png";
import { useMangaCollection } from "../entities";
import { MangaGrid } from "../widgets";

/** /lector — the manga collection: mascot + blurb and the pool link on top, the
 *  manga grid below. View mode is read-only browsing; Edit mode reveals the "add
 *  manga" tile and per-cover upload buttons. */
export function MangaCollectionPage() {
  const navigate = useNavigate();
  const { mangas, loading, error } = useMangaCollection();
  const [editing, setEditing] = useState(false);

  // Initial load — show only the mascot dialog, nothing else on the page yet.
  if (loading && mangas.length === 0) {
    return <LoadingDialog fullScreen={false} message="Fetching your library…" />;
  }
  if (error) {
    return <p className="py-12 text-center text-sm text-[var(--owl-brown-muted)]">Couldn't load your library.</p>;
  }

  return (
    <div className="md:h-full md:overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-6 py-6 flex flex-col gap-6">
        <header className="flex items-center gap-3">
          <img src={owlMascot} alt="" aria-hidden="true" className="w-10" />
          <div className="flex-1 min-w-0">
            <h1 className="text-xl text-[var(--owl-brown-dark)]">Lector</h1>
            <p className="text-sm text-[var(--owl-brown-muted)]">Your manga library.</p>
          </div>
          <button
            onClick={() => setEditing((e) => !e)}
            className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer"
          >
            {editing ? <Check size={15} aria-hidden="true" /> : <Pencil size={15} aria-hidden="true" />}
            {editing ? "Done" : "Edit"}
          </button>
          <button
            onClick={() => navigate("/lector/pool")}
            className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer"
          >
            <Layers size={15} aria-hidden="true" />
            Image pool
          </button>
        </header>

        <MangaGrid editing={editing} />
      </div>
    </div>
  );
}
