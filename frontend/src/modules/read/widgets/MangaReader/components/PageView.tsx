import type { Page } from "../../../entities";

interface PageViewProps {
  page: Page;
  /** Signed CDN URL for the page's Storage object. */
  imageUrl?: string;
  /** Laid over the image (edit mode's controls). */
  children?: React.ReactNode;
}

export function PageView({ page, imageUrl, children }: PageViewProps) {
  // Reserve the box from the stored intrinsic dims → no layout shift while the
  // image streams in. content-visibility lets the browser skip off-screen work
  // (the lightweight stand-in for full list virtualization).
  const aspectRatio = page.width && page.height ? `${page.width} / ${page.height}` : "3 / 4";

  return (
    <div
      className="relative w-full bg-[var(--owl-cream-mid)]/30"
      style={{
        aspectRatio,
        contentVisibility: "auto",
        containIntrinsicSize: page.height ? `auto ${page.height / 16}rem` : "auto 60rem",
      }}
    >
      {imageUrl && (
        <img
          src={imageUrl}
          alt={`Page ${page.position + 1}`}
          loading="lazy"
          decoding="async"
          className="size-full object-contain"
        />
      )}
      {children}
    </div>
  );
}
