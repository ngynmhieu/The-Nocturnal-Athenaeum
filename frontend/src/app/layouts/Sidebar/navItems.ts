import { MessageSquare } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItemConfig {
  path: string;
  label: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItemConfig[] = [
  { path: "/", label: "The Docent", icon: MessageSquare },
];
