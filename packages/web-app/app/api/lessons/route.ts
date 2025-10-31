import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    createLessonCommand,
    getLessonsByUserId,
    getUserByEmail,
} from "@core/index";


export async function POST(req: Request) {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await req.json().catch(() => null);
    const topic = typeof body?.topic === "string" ? body.topic.trim() : "";
    const vocabulary = typeof body?.vocabulary === "string" ? body.vocabulary.trim() : "";

    if (!topic) {
        return NextResponse.json({ error: "Lesson topic is required" }, { status: 400 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const created = await createLessonCommand({
        userId: user._id,
        topic,
        vocabulary
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

    const lessons = await getLessonsByUserId(user._id);

    return NextResponse.json({ data: lessons });
}
