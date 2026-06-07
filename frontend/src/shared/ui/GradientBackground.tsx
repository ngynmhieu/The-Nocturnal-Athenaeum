import { ReactNode } from "react";

interface GradientBackgroundProps {
  children: ReactNode;
  className?: string;
}

export function GradientBackground({ children, className = "" }: GradientBackgroundProps) {
  return (
    <div className={`relative min-h-screen ${className}`}>
      <div className="fixed inset-0 overflow-hidden pointer-events-none bg-[var(--owl-parchment)]">
        <div
          className="absolute w-[35vw] h-[35vw] rounded-full blur-[5vw] opacity-45"
          style={{
            background: "radial-gradient(circle, var(--owl-brown-mid) 0%, var(--owl-brown) 60%, transparent 100%)",
            top: "-8vw",
            left: "-6vw",
            animation: "drift 20s ease-in-out infinite alternate",
          }}
        />
        <div
          className="absolute w-[28vw] h-[28vw] rounded-full blur-[5vw] opacity-45"
          style={{
            background: "radial-gradient(circle, var(--owl-tan) 0%, var(--owl-tan-mid) 60%, transparent 100%)",
            top: "30%",
            right: "-5vw",
            animation: "drift 16s ease-in-out infinite alternate",
            animationDelay: "-4s",
          }}
        />
        <div
          className="absolute w-[20vw] h-[20vw] rounded-full blur-[5vw] opacity-45"
          style={{
            background: "radial-gradient(circle, var(--owl-cream) 0%, var(--owl-cream-mid) 60%, transparent 100%)",
            bottom: "8vh",
            left: "20%",
            animation: "drift 22s ease-in-out infinite alternate",
            animationDelay: "-8s",
          }}
        />
        <div
          className="absolute w-[30vw] h-[30vw] rounded-full blur-[5vw] opacity-45"
          style={{
            background: "radial-gradient(circle, var(--owl-brown) 0%, var(--owl-brown-deep) 60%, transparent 100%)",
            bottom: "-10vw",
            right: "10%",
            animation: "drift 18s ease-in-out infinite alternate",
            animationDelay: "-12s",
          }}
        />
        <div
          className="absolute w-[16vw] h-[16vw] rounded-full blur-[5vw] opacity-25"
          style={{
            background: "radial-gradient(circle, var(--owl-orange) 0%, var(--owl-orange-deep) 60%, transparent 100%)",
            top: "50%",
            left: "50%",
            animation: "drift-center 24s ease-in-out infinite",
            animationDelay: "-6s",
          }}
        />
      </div>

      <div className="relative z-10 h-full">{children}</div>
    </div>
  );
}
