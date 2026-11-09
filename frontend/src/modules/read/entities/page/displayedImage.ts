import type { Page } from "./page.types";

export interface DisplayedImage {
  path: string;
  width: number | null;
  height: number | null;
  label: "Original" | "English" | "Upscaled";
}

/** Which of a page's images the reader shows: the English translation if there
 *  is one, else the upscale, else the original. `showOriginal` forces the original. */
export function displayedImage(page: Page, showOriginal: boolean): DisplayedImage {
  const original: DisplayedImage = {
    path: page.storagePath,
    width: page.width,
    height: page.height,
    label: "Original",
  };
  if (showOriginal) return original;
  const versions = page.versions ?? [];
  const translated = versions.find((v) => v.kind === "translated" && v.language === "en");
  if (translated) {
    return { path: translated.storagePath, width: translated.width, height: translated.height, label: "English" };
  }
  const upscaled = versions.find((v) => v.kind === "upscaled");
  if (upscaled) {
    return { path: upscaled.storagePath, width: upscaled.width, height: upscaled.height, label: "Upscaled" };
  }
  return original;
}
