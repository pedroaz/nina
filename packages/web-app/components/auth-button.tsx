"use client";

import { signIn, signOut } from "next-auth/react";
import { LogOut, LogIn } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { useUserStore } from "@/stores/user-store";

export function AuthButton() {
    const session = useUserStore((state) => state.session);
    const status = useUserStore((state) => state.status);

    if (status === "loading") {
        return <Skeleton className="h-12 w-full rounded-xl" />;
    }

    if (session) {
        return (
            <button
                onClick={() => signOut()}
                className="w-full btn-playful bg-error-bg border-error-text text-error-text hover:bg-error/10 py-3 text-base flex items-center justify-center gap-2"
            >
                <LogOut className="h-4 w-4" />
                <span>Sign Out</span>
            </button>
        );
    }

    return (
        <button
            onClick={() => signIn("google")}
            className="w-full btn-playful btn-primary-playful py-3 text-base flex items-center justify-center gap-2"
        >
            <LogIn className="h-4 w-4" />
            <span>Sign In with Google</span>
        </button>
    );
}
