"use client";

import { useTransition } from "react";
import { signOut } from "next-auth/react";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";

export function SignOutButton() {
    const [isPending, startTransition] = useTransition();

    const handleSignOut = () => {
        startTransition(() => {
            void signOut();
        });
    };

    return (
        <Button
            type="button"
            variant="destructive"
            onClick={handleSignOut}
            disabled={isPending}
            className="w-full py-6 text-base"
        >
            <LogOut className="h-4 w-4 mr-2" aria-hidden="true" />
            <span>{isPending ? "Signing out..." : "Sign out"}</span>
        </Button>
    );
}
