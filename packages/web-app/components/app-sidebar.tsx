"use client";

import Link from "next/link";
import type { ComponentProps } from "react";
import { Home, User, BookOpen, Users, Map, CreditCard, Dumbbell, Target } from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarHeader,
  SidebarMenuButton,
  SidebarRail,
} from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { useUserStore } from "@/stores/user-store";

// Navigation data with icons
const data = {
  navMain: [
    {
      title: "Home",
      url: "/",
      icon: Home,
    },
    {
      title: "Lessons",
      url: "/lessons",
      icon: BookOpen,
    },
    {
      title: "Flash Cards",
      url: "/flash-cards",
      icon: CreditCard,
    },
    {
      title: "Exercises",
      url: "/exercises",
      icon: Dumbbell,
    },
    {
      title: "Missions",
      url: "/missions",
      icon: Target,
    },
    {
      title: "Learning Path",
      url: "/learning-path",
      icon: Map,
    },
    {
      title: "Community",
      url: "/community",
      icon: Users,
    },
  ],
};

export function AppSidebar({ ...props }: ComponentProps<typeof Sidebar>) {
  const session = useUserStore((state) => state.session);
  const status = useUserStore((state) => state.status);

  return (
    <Sidebar {...props}>
      <SidebarHeader className="p-4">
        {status === "loading" ? (
          <Skeleton className="h-16 w-full rounded-2xl" />
        ) : session?.user ? (
          <Link
            href="/profile"
            className="flex items-center gap-3 rounded-2xl border border-orange-100 bg-orange-50/60 px-4 py-3 text-left transition hover:border-orange-200 hover:bg-orange-100"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-orange-600">
              <User className="h-5 w-5" aria-hidden="true" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-bold text-neutral-900">{session.user.name || session.user.email}</p>
            </div>
          </Link>
        ) : null}
      </SidebarHeader>

      <SidebarContent className="p-3">
        <div className="space-y-2">
          {data.navMain.map((item) => {
            const Icon = item.icon;
            return (
              <SidebarGroup key={item.title} className="p-0">
                <SidebarMenuButton asChild className="p-0">
                  <Link
                    href={item.url}
                    className="flex items-center gap-3 rounded-xl border-2 border-transparent px-4 py-3 font-semibold text-neutral-900 transition-all hover:border-orange-200 hover:bg-orange-50 hover:text-orange-700 hover:shadow-[2px_2px_0px_0px_rgba(251,146,60,0.3)]"
                  >
                    <Icon className="h-5 w-5" aria-hidden="true" />
                    <span>{item.title}</span>
                  </Link>
                </SidebarMenuButton>
              </SidebarGroup>
            );
          })}
        </div>
      </SidebarContent>

      <SidebarRail />
    </Sidebar>
  );
}
