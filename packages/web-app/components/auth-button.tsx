"use client";

import { useSession, signIn, signOut } from "next-auth/react";
import { LogOut, LogIn } from "lucide-react";

export function AuthButton() {
    const { data: session } = useSession();

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
