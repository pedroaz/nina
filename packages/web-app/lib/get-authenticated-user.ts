import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { getUserByEmail } from "@core/index";

export async function getAuthenticatedUser(redirectPath?: string) {
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin${redirectPath ? `?callbackUrl=${encodeURIComponent(redirectPath)}` : ""}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        redirect(signInUrl);
    }

    return user;
}

export async function getAuthenticatedSession(redirectPath?: string) {
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin${redirectPath ? `?callbackUrl=${encodeURIComponent(redirectPath)}` : ""}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    return session;
}
