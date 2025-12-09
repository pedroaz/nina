"use client";

import { SessionProvider, useSession } from "next-auth/react";
import type { Session } from "next-auth";
import { useEffect, type ReactNode } from "react";

import { useUserStore } from "@/stores/user-store";

interface ProvidersProps {
    readonly children: ReactNode;
    readonly initialSession?: Session | null;
}

let hasInitializedUserStore = false;

export function Providers({ children, initialSession = null }: ProvidersProps) {
    if (!hasInitializedUserStore) {
        useUserStore.setState({
            session: initialSession,
            status: initialSession ? "authenticated" : "unauthenticated",
            hasResolved: true,
        });
        hasInitializedUserStore = true;
    }

    return (
        <SessionProvider session={initialSession ?? undefined} refetchOnWindowFocus={false}>
            <UserSessionBridge>{children}</UserSessionBridge>
        </SessionProvider>
    );
}

function UserSessionBridge({ children }: { children: ReactNode }) {
    const { data: session, status } = useSession();
    const setStateFromSession = useUserStore((state) => state.setStateFromSession);

    useEffect(() => {
        setStateFromSession(session ?? null, status);
    }, [session, status, setStateFromSession]);

    return <>{children}</>;
}
