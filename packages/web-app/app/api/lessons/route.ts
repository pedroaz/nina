import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    createLessonCommand,
    getLessonsByCreatorId,
    getUserByEmail,
} from "@core/index";


export async function POST(req: Request) {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await req.json().catch(() => null);
    const userPrompt = typeof body?.userPrompt === "string" ? body.userPrompt.trim() : "";

    if (!userPrompt) {
        return NextResponse.json({ error: "User prompt is required" }, { status: 400 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const created = await createLessonCommand({
        creatorId: user.id,
        userPrompt,
    });

    return NextResponse.json(created, { status: 201 });
}

export async function GET() {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const lessons = await getLessonsByCreatorId(user.id);

    return NextResponse.json({ data: lessons });
}
