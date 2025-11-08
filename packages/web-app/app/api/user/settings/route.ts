import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    updateFlashCardDisplayPreferenceCommand,
    getUserByEmail,
} from "@core/index";

export async function GET() {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    return NextResponse.json(user);
}

export async function PATCH(req: Request) {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const body = await req.json().catch(() => null);
    const { flashCardDisplayPreference } = body || {};

    if (
        flashCardDisplayPreference &&
        !['base-first', 'german-first'].includes(flashCardDisplayPreference)
    ) {
        return NextResponse.json(
            { error: "Invalid flashCardDisplayPreference. Must be 'base-first' or 'german-first'" },
            { status: 400 }
        );
    }

    const updatedUser = await updateFlashCardDisplayPreferenceCommand({
        userId: user._id,
        preference: flashCardDisplayPreference,
    });

    return NextResponse.json(updatedUser);
}
