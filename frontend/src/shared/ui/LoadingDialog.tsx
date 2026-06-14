import { motion } from "motion/react";
import { GradientBackground } from "./GradientBackground";
import owlRunning from "@/shared/assets/owl_running_with_glasses.png";

interface LoadingDialogProps {
  message?: string;
}

/**
 * Full-viewport "please wait" loader. Paints its own GradientBackground (so it
 * looks right even when no page is rendered behind it) with a dialog card and a
 * running owl on top. Used for the post-login boot gate and as the Suspense
 * fallback while a lazily-loaded page chunk downloads.
 */
export function LoadingDialog({ message = "Just a moment…" }: LoadingDialogProps) {
  return (
    <div className="fixed inset-0 z-50">
      <GradientBackground>
        <div className="flex h-screen items-center justify-center px-6">
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="flex flex-col items-center gap-6 rounded-3xl border border-[var(--owl-brown)]/15 bg-[var(--owl-parchment)]/70 px-16 py-14 shadow-lg backdrop-blur-md"
          >
            {/* Running owl — bobs and tilts to look like it's dashing in place */}
            <motion.img
              src={owlRunning}
              alt=""
              className="h-36 w-36 object-contain drop-shadow-md"
              animate={{ y: [0, -7, 0], rotate: [-4, 4, -4] }}
              transition={{ duration: 0.5, ease: "easeInOut", repeat: Infinity }}
            />

            {/* Indeterminate track — a sliver that runs forward, implying motion */}
            <div className="h-1 w-40 overflow-hidden rounded-full bg-[var(--owl-brown)]/15">
              <motion.div
                className="h-full w-1/3 rounded-full bg-[var(--owl-brown)]"
                animate={{ x: ["-120%", "320%"] }}
                transition={{ duration: 1, ease: "easeInOut", repeat: Infinity }}
              />
            </div>

            <span className="text-base font-medium text-[var(--owl-brown-deep)]">{message}</span>
          </motion.div>
        </div>
      </GradientBackground>
    </div>
  );
}
