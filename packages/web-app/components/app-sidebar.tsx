"use client";

import type { ComponentProps } from "react";
import { useSession } from "next-auth/react";

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

// This is sample data.
const data = {
  navMain: [
    {
      title: "Home",
      url: "/",
    },
    {
      title: "Profile",
      url: "/profile",
    },
    {
      title: "Lessons",
      url: "/lessons",
    },
    {
      title: "Community",
      url: "/community",
    },
    {
      title: "Learning Path",
      url: "/learning-path",
    },
    {
      title: "Flash Cards",
      url: "/flash-cards",
    },
    {
      title: "Exercises",
      url: "/exercises",
    },
  ],
};

export function AppSidebar({ ...props }: ComponentProps<typeof Sidebar>) {
  const { data: session, status } = useSession();

  return (
    <Sidebar {...props}>
      <SidebarHeader>
        <div className="min-h-4">
          {status === "loading" ? (
            <Skeleton className="h-4 w-48" />
          ) : (
            session?.user?.email || ""
          )}
        </div>
      </SidebarHeader>
      <SidebarContent>
        {data.navMain.map((item) => (
          <SidebarGroup key={item.title}>
            <SidebarMenuButton asChild>
              <a href={item.url}>{item.title}</a>
            </SidebarMenuButton>
          </SidebarGroup>
        ))}
      </SidebarContent>
      <SidebarRail />
      <SidebarFooter>
        <AuthButton></AuthButton>
      </SidebarFooter>
    </Sidebar>
  );
}
