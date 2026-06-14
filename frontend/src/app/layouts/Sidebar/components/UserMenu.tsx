import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence } from "motion/react";
import { User, LogOut } from "lucide-react";
import { useSession, useLogout } from "@/modules/auth";
import { Dropdown, DropdownSection, DropdownItem } from "@/shared/ui";

interface UserMenuProps {
  open: boolean;
}

export function UserMenu({ open }: UserMenuProps) {
  const { user } = useSession();
  const { logout } = useLogout();
  const [menuOpen, setMenuOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ top: 0, left: 0 });

  const handleToggle = () => {
    if (!menuOpen && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setPos({ top: rect.top, left: rect.right + 8 });
    }
    setMenuOpen((v) => !v);
  };

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        !triggerRef.current?.contains(e.target as Node) &&
        !dropdownRef.current?.contains(e.target as Node)
      ) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="relative w-full">
      <button
        ref={triggerRef}
        onClick={handleToggle}
        aria-label="User menu"
        className={`flex items-center gap-3 px-2 h-14 rounded-lg w-full transition-colors cursor-pointer ${open ? "hover:bg-[var(--owl-brown)]/10" : ""}`}
      >
        <Avatar user={user} />
        {open && user && (
          <div className="overflow-hidden min-w-0 text-left">
            <p className="text-xs font-medium text-[var(--owl-brown-deep)] whitespace-nowrap truncate">
              {user.fullName ?? user.email}
            </p>
            <p className="text-xs text-[var(--owl-brown-muted)] whitespace-nowrap truncate">
              {user.email}
            </p>
          </div>
        )}
      </button>

      {createPortal(
        <AnimatePresence>
          {menuOpen && (
            <div
              ref={dropdownRef}
              style={{ position: "fixed", top: pos.top, left: pos.left }}
              className="ml-2 -translate-y-[50%] z-50"
            >
              <Dropdown>
                {user && (
                  <DropdownSection>
                    <p className="text-xs font-medium text-[var(--owl-brown-deep)] truncate">{user.fullName ?? ""}</p>
                    <p className="text-xs text-[var(--owl-brown-muted)] truncate">{user.email}</p>
                  </DropdownSection>
                )}
                <DropdownItem icon={<LogOut size={13} />} onClick={() => { logout(); setMenuOpen(false); }}>
                  Sign out
                </DropdownItem>
              </Dropdown>
            </div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}

interface AvatarProps {
  user: { avatarUrl: string | null; fullName: string | null } | null;
}

function Avatar({ user }: AvatarProps) {
  const cls = "shrink-0 w-6 h-6 rounded-full overflow-hidden bg-[var(--owl-brown)]/20 flex items-center justify-center";
  if (user?.avatarUrl) {
    return (
      <div className={cls}>
        <img src={user.avatarUrl} alt="" className="w-full h-full object-cover" referrerPolicy="no-referrer" />
      </div>
    );
  }
  return (
    <div className={cls}>
      <User size={12} className="text-[var(--owl-brown)] object-cover" />
    </div>
  );
}
