"use client";

import { useSession, signIn, signOut } from "next-auth/react";
import { Button } from "./ui/button";

export function AuthButton() {
    const { data: session } = useSession();

    if (session) {
        return (
            <div className="flex items-center gap-4">
                <Button onClick={() => signOut()}>Sign Out</Button>
            </div>
        );
    }

    return <Button onClick={() => signIn("google")}>Sign In with Google</Button>;
}
