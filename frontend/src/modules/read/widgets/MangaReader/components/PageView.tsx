import type { Page, DisplayedImage } from "../../../entities";

interface PageViewProps {
  page: Page;
  /** The image being shown (original or an accepted version); its dims set the box. */
  image: DisplayedImage;
  /** Signed CDN URL for that image's Storage object. */
  imageUrl?: string;
  /** This page's index in the reader — lets `Reader` observe which page is on screen. */
  index: number;
  /** Start downloading now instead of when the browser decides it's close enough
   *  (`Reader` sets this for the pages just ahead of the one being read). */
  eager?: boolean;
  /** Present when the page has an accepted version: a pill flipping to the original. */
  originalToggle?: { label: string; showingOriginal: boolean; onToggle: () => void };
  /** Laid over the image (edit mode's controls). */
  children?: React.ReactNode;
}

export function PageView({ page, image, imageUrl, index, eager = false, originalToggle, children }: PageViewProps) {
  // Reserve the box from the stored intrinsic dims → no layout shift while the
  // image streams in. content-visibility lets the browser skip off-screen work
  // (the lightweight stand-in for full list virtualization).
  const aspectRatio = image.width && image.height ? `${image.width} / ${image.height}` : "3 / 4";

  return (
    <div
      data-page-index={index}
      className="relative w-full bg-[var(--owl-cream-mid)]/30"
      style={{
        aspectRatio,
        contentVisibility: "auto",
        containIntrinsicSize: image.height ? `auto ${image.height / 16}rem` : "auto 60rem",
      }}
    >
      {imageUrl && (
        <img
          src={imageUrl}
          alt={`Page ${page.position + 1}`}
          // lazy → eager on an existing <img> starts its download immediately.
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          className="size-full object-contain"
        />
      )}
      {originalToggle && (
        <button
          type="button"
          onClick={originalToggle.onToggle}
          aria-label={originalToggle.showingOriginal ? `Show ${originalToggle.label}` : "Show original"}
          className="absolute bottom-[1.5%] right-[1.5%] z-10 flex items-center overflow-hidden rounded-full border border-[var(--owl-border)] bg-[var(--owl-cream)]/90 text-xs shadow-sm backdrop-blur-sm cursor-pointer"
        >
          <span
            className={`px-[0.6rem] py-[0.2rem] transition-colors ${
              originalToggle.showingOriginal
                ? "bg-[var(--owl-brown-mid)]/20 font-semibold text-[var(--owl-brown-deep)]"
                : "text-[var(--owl-brown-muted)]"
            }`}
          >
            Original
          </span>
          <span
            className={`px-[0.6rem] py-[0.2rem] transition-colors ${
              originalToggle.showingOriginal
                ? "text-[var(--owl-brown-muted)]"
                : "bg-[var(--owl-brown-mid)]/20 font-semibold text-[var(--owl-brown-deep)]"
            }`}
          >
            {originalToggle.label}
          </span>
        </button>
      )}
      {children}
    </div>
  );
}
