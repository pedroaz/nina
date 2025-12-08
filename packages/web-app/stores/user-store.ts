'use client';

import { create } from "zustand";
import type { Session } from "next-auth";

type SessionStatus = "loading" | "authenticated" | "unauthenticated";

interface UserStoreState {
    readonly session: Session | null;
    readonly status: SessionStatus;
    readonly hasResolved: boolean;
    setStateFromSession: (session: Session | null, status: SessionStatus) => void;
}

export const useUserStore = create<UserStoreState>((set) => ({
    session: null,
    status: "loading",
    hasResolved: false,
    setStateFromSession: (session, status) =>
        set((state) => {
            if (status === "loading" && state.hasResolved) {
                return state;
            }

            return {
                session,
                status,
                hasResolved: status === "loading" ? state.hasResolved : true,
            };
        }),
}));
