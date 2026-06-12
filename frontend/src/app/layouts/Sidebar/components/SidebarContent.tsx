import { useLocation } from "react-router";
import { NAV_ITEMS } from "../navItems";
import { NavItem } from "./NavItem";

interface SidebarContentProps {
  open: boolean;
}

export function SidebarContent({ open }: SidebarContentProps) {
  const location = useLocation();

  return (
    <div className="flex-1 overflow-y-auto overflow-x-hidden py-2">
      {NAV_ITEMS.map((item) => (
        <NavItem
          key={item.path}
          to={item.path}
          label={item.label}
          icon={item.icon}
          active={location.pathname === item.path}
          open={open}
        />
      ))}
    </div>
  );
}
