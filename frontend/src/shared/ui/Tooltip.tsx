import { useState, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

interface TooltipProps {
  content: string;
  children: ReactNode;
  side?: "top" | "right" | "bottom" | "left";
  disabled?: boolean;
}

const GAP = 8;

export function Tooltip({ content, children, side = "right", disabled = false }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const triggerRef = useRef<HTMLDivElement>(null);

  const handleMouseEnter = () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();

    const positions = {
      right:  { top: rect.top + rect.height / 2, left: rect.right + GAP },
      left:   { top: rect.top + rect.height / 2, left: rect.left - GAP },
      top:    { top: rect.top - GAP,              left: rect.left + rect.width / 2 },
      bottom: { top: rect.bottom + GAP,           left: rect.left + rect.width / 2 },
    };

    setCoords(positions[side]);
    setVisible(true);
  };

  if (disabled) return <>{children}</>;

  return (
    <>
      <div
        ref={triggerRef}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setVisible(false)}
      >
        {children}
      </div>
      {visible && createPortal(
        <div
          className="fixed z-50 pointer-events-none"
          style={{
            top: coords.top,
            left: coords.left,
            transform: side === "right"  ? "translateY(-50%)"
                     : side === "left"   ? "translate(-100%, -50%)"
                     : side === "top"    ? "translate(-50%, -100%)"
                     : "translateX(-50%)",
          }}
        >
          <div className="px-2 py-1 rounded-md text-xs whitespace-nowrap bg-[var(--owl-brown-dark)] text-[var(--owl-cream)] shadow-md">
            {content}
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
