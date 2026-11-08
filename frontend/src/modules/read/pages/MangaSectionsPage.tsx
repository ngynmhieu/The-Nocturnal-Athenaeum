import { useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router";
import { ArrowLeft, Pencil, Check, Link } from "lucide-react";
import { LoadingDialog } from "@/shared/ui";
import { useMangaDetail, type Section, type SectionKind } from "../entities";
import { useCreateSection, useDeleteSection } from "../features";
import { SectionTabs, SectionGrid, PullSeriesModal } from "../widgets";

/** /lector/manga/:mangaId — one series: Volumes/Chapters tabs, create/delete
 *  sections, and set a section's cover. Adding pages happens on the reader
 *  itself (its own edit mode) — this page only manages the sections list.
 *  Same view/edit split as the collection: view is read-only, edit reveals the
 *  add-section tile, per-card hover actions, and (on Volumes) "Pull series" —
 *  create + fill every volume from a series link (see `PullSeriesModal`). */
export function MangaSectionsPage() {
  const { mangaId } = useParams();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const tab: SectionKind = searchParams.get("tab") === "volumes" ? "volume" : "chapter";

  const { detail, notFound, refresh } = useMangaDetail(mangaId);
  const [editing, setEditing] = useState(false);
  const [seriesOpen, setSeriesOpen] = useState(false);

  const { createSection, creating } = useCreateSection();
  const { deleteSection: deleteSectionApi } = useDeleteSection();

  if (notFound) {
    return <p className="py-12 text-center text-sm text-[var(--owl-brown-muted)]">Manga not found.</p>;
  }
  if (!detail) {
    return <LoadingDialog fullScreen={false} message="Fetching your manga…" />;
  }

  const sections = detail.sections.filter((s) => s.kind === tab);

  const addSection = async (input: { number: number | null; title: string | null }) => {
    const section = await createSection(detail.id, { kind: tab, ...input });
    await refresh();
    // Fresh section has no pages yet — go straight to the reader's edit mode to add some.
    navigate(`/lector/manga/${detail.id}/read/${section.id}?edit=1`);
  };

  const deleteSection = async (section: Section) => {
    await deleteSectionApi(section.id);
    await refresh();
  };

  return (
    <div className="md:h-full md:overflow-y-auto">
      <div className="mx-auto w-full max-w-5xl px-6 py-6 flex flex-col gap-5">
        <header className="flex items-center gap-3">
          <button
            onClick={() => navigate("/lector")}
            aria-label="Back to collection"
            className="p-1.5 rounded-md text-[var(--owl-brown-muted)] transition-colors hover:bg-[var(--owl-brown-mid)]/10 hover:text-[var(--owl-brown-deep)] cursor-pointer"
          >
            <ArrowLeft size={24} />
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-xl text-[var(--owl-brown-dark)] truncate">{detail.title}</h1>
            {detail.description && (
              <p className="text-sm text-[var(--owl-brown-muted)] truncate">{detail.description}</p>
            )}
          </div>
          {editing && tab === "volume" && (
            <button
              onClick={() => setSeriesOpen(true)}
              className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer"
            >
              <Link size={15} aria-hidden="true" />
              Pull series
            </button>
          )}
          <button
            onClick={() => setEditing((e) => !e)}
            className="flex items-center gap-1.5 rounded-md border border-[var(--owl-border)] px-3 py-1.5 text-sm text-[var(--owl-brown)] hover:bg-[var(--owl-brown-mid)]/10 transition-colors cursor-pointer"
          >
            {editing ? <Check size={15} aria-hidden="true" /> : <Pencil size={15} aria-hidden="true" />}
            {editing ? "Done" : "Edit"}
          </button>
        </header>

        <SectionTabs
          active={tab}
          onChange={(kind) => setSearchParams({ tab: kind === "chapter" ? "chapters" : "volumes" })}
        />

        <SectionGrid
          kind={tab}
          sections={sections}
          editing={editing}
          onOpen={(section) => navigate(`/lector/manga/${detail.id}/read/${section.id}`)}
          onCoverChanged={refresh}
          onDelete={deleteSection}
          onCreate={addSection}
          creating={creating}
        />
      </div>

      <PullSeriesModal
        open={seriesOpen}
        onClose={() => setSeriesOpen(false)}
        mangaId={detail.id}
        existingNumbers={detail.sections.filter((s) => s.kind === "volume").map((s) => s.number)}
        onPulled={refresh}
      />
    </div>
  );
}
