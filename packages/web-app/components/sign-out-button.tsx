"use client";

import { useTransition } from "react";
import { signOut } from "next-auth/react";
import { LogOut } from "lucide-react";

export function SignOutButton() {
    const [isPending, startTransition] = useTransition();

    const handleSignOut = () => {
        startTransition(() => {
            void signOut();
        });
    };

    return (
        <button
            type="button"
            onClick={handleSignOut}
            disabled={isPending}
            className="w-full btn-playful bg-error-bg border-error-text text-error-text hover:bg-error/10 py-3 text-base flex items-center justify-center gap-2 disabled:opacity-70"
        >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            <span>{isPending ? "Signing out..." : "Sign out"}</span>
        </button>
    );
}
