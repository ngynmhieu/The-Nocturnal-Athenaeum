import { motion } from "motion/react";
import { GradientBackground } from "@/shared/ui";
import owlMascot from "@/shared/assets/owl_reading_book_with_glasses.png";
import { LoginButton } from "../widgets";

export function LoginPage() {
  return (
    <GradientBackground>
      <div className="flex h-screen flex-col items-center justify-center px-6">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="flex w-full max-w-md flex-col items-center gap-6 rounded-2xl border border-[var(--owl-brown)]/15 bg-[var(--owl-parchment)]/60 px-5 py-12 shadow-lg backdrop-blur-md"
        >
          <motion.img
            src={owlMascot}
            alt="The Nocturnal Athenaeum owl"
            className="h-40 w-40 object-contain drop-shadow-md"
            animate={{ y: [0, -8, 0] }}
            transition={{ duration: 4, ease: "easeInOut", repeat: Infinity }}
          />

          <div className="text-center">
            <h1 className="text-2xl font-semibold tracking-wide text-[var(--owl-brown-deep)]">
              THE NOCTURNAL ATHENAEUM
            </h1>
            <p className="mt-1.5 text-sm text-[var(--owl-brown-muted)]">
              Your after-hours workspace
            </p>
          </div>

          <div className="my-1 h-px w-16 bg-[var(--owl-brown)]/15" />

          <LoginButton />

          <p className="text-center text-xs text-[var(--owl-brown-muted)]/80">
            Sign in to pick up where you left off
          </p>
        </motion.div>
      </div>
    </GradientBackground>
  );
}
