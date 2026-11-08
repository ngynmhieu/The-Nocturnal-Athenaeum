import { useCallback, useState } from "react";
import { readApi } from "../../../shared";

/** Remove one page from its section — the row and its Storage object. The
 *  backend closes the gap (later pages move up one) in the same transaction. */
export function useDeletePage() {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const deletePage = useCallback(async (pageId: string): Promise<void> => {
    setDeletingId(pageId);
    try {
      await readApi.deletePage(pageId);
    } finally {
      setDeletingId(null);
    }
  }, []);

  return { deletePage, deletingId };
}
