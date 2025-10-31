import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    createLessonRequestCommand,
    getLessonRequestsByCreatorId,
    getUserByEmail,
} from "@core/index";
import type { LessonRequest } from "@core/index";

function serializeLessonRequest(request: LessonRequest) {
    return {
        id: request.id,
        creatorId: request.creatorId,
        prompt: request.prompt,
        lessonId: request.lessonId,
        status: request.status,
        createdAt: request.createdAt?.toISOString?.() ?? null,
        updatedAt: request.updatedAt?.toISOString?.() ?? null,
    };
}

export async function POST(req: Request) {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await req.json().catch(() => null);
    const prompt = typeof body?.prompt === "string" ? body.prompt.trim() : "";

    if (!prompt) {
        return NextResponse.json({ error: "Prompt is required" }, { status: 400 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const created = await createLessonRequestCommand({
        creatorId: user.id,
        prompt,
    });

    return NextResponse.json(serializeLessonRequest(created), { status: 201 });
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

    const requests = await getLessonRequestsByCreatorId(user.id);

    return NextResponse.json({ data: requests.map(serializeLessonRequest) });
}
