"use client";

import type { ComponentProps } from "react";
import { useSession } from "next-auth/react";
import { Home, User, BookOpen, Users, Map, CreditCard, Dumbbell, Target } from "lucide-react";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarHeader,
  SidebarMenuButton,
  SidebarRail,
} from "@/components/ui/sidebar";
import { Skeleton } from "@/components/ui/skeleton";
import { AuthButton } from "./auth-button";

// Navigation data with icons
const data = {
  navMain: [
    {
      title: "Home",
      url: "/",
      icon: Home,
      emoji: "🏠",
    },
    {
      title: "Profile",
      url: "/profile",
      icon: User,
      emoji: "👤",
    },
    {
      title: "Lessons",
      url: "/lessons",
      icon: BookOpen,
      emoji: "📚",
    },
    {
      title: "Flash Cards",
      url: "/flash-cards",
      icon: CreditCard,
      emoji: "🃏",
    },
    {
      title: "Exercises",
      url: "/exercises",
      icon: Dumbbell,
      emoji: "💪",
    },
    {
      title: "Missions",
      url: "/missions",
      icon: Target,
      emoji: "🎯",
    },
    {
      title: "Learning Path",
      url: "/learning-path",
      icon: Map,
      emoji: "🗺️",
    },
    {
      title: "Community",
      url: "/community",
      icon: Users,
      emoji: "👥",
    },
  ],
};

export function AppSidebar({ ...props }: ComponentProps<typeof Sidebar>) {
  const { data: session, status } = useSession();

  return (
    <Sidebar {...props}>
      <SidebarHeader className="p-4">
        {status === "loading" ? (
          <Skeleton className="h-16 w-full rounded-2xl" />
        ) : session?.user ? (
          <div className="card-playful bg-gradient-to-br from-orange-50 to-teal-50 p-4">
            <div className="flex items-center gap-3">
              <div className="icon-bubble bg-white flex-shrink-0">
                <User className="h-5 w-5 text-orange-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-neutral-600 uppercase tracking-wide">Welcome back!</p>
                <p className="text-sm font-extrabold text-neutral-900 truncate">{session.user.name || session.user.email}</p>
              </div>
            </div>
          </div>
        ) : null}
      </SidebarHeader>

      <SidebarContent className="p-3">
        <div className="space-y-2">
          {data.navMain.map((item) => (
            <SidebarGroup key={item.title} className="p-0">
              <SidebarMenuButton asChild className="p-0">
                <a
                  href={item.url}
                  className="flex items-center gap-3 px-4 py-3 rounded-xl font-bold text-neutral-900 hover:bg-orange-50 hover:text-orange-700 transition-all border-2 border-transparent hover:border-orange-200 hover:shadow-[2px_2px_0px_0px_rgba(251,146,60,0.3)]"
                >
                  <span className="text-xl">{item.emoji}</span>
                  <span>{item.title}</span>
                </a>
              </SidebarMenuButton>
            </SidebarGroup>
          ))}
        </div>
      </SidebarContent>

      <SidebarRail />

      <SidebarFooter className="p-4">
        <AuthButton />
      </SidebarFooter>
    </Sidebar>
  );
}
