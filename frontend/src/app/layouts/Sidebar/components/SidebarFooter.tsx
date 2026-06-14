import { useSession, LoginButton } from "@/modules/auth";
import { UserMenu } from "./UserMenu";

interface SidebarFooterProps {
  open: boolean;
}

export function SidebarFooter({ open }: SidebarFooterProps) {
  const { status } = useSession();

  return (
    <div className="shrink-0 border-t border-[var(--owl-brown)]/10">
      {status === "authenticated" ? (
        <UserMenu open={open} />
      ) : status === "anonymous" ? (
        <div className={`flex ${open ? "justify-start" : "justify-center"}`}>
          <LoginButton />
        </div>
      ) : null}
    </div>
  );
}
