import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    createLessonCommand,
    getLessonsByUserId,
    getUserByEmail,
} from "@core/index";
import { MODEL_CATEGORIES, getModelConfig } from "@core/llm/llm";


export async function POST(req: Request) {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await req.json().catch(() => null);
    const topic = typeof body?.topic === "string" ? body.topic.trim() : "";
    const vocabulary = typeof body?.vocabulary === "string" ? body.vocabulary.trim() : "";
    const modelType = body?.modelType === "fast" || body?.modelType === "detailed"
        ? body.modelType
        : "detailed";

    if (!topic) {
        return NextResponse.json({ error: "Lesson topic is required" }, { status: 400 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const modelCategory = modelType === "fast" ? MODEL_CATEGORIES.FAST : MODEL_CATEGORIES.DETAILED;
    const modelConfig = getModelConfig(modelCategory);
    const startTime = performance.now();

    console.log(`[Lesson API] Creating lesson for user: ${user.email}`);
    console.log(`[Lesson API] Using model: ${modelConfig.displayName}`);
    console.log(`[Lesson API] Topic: "${topic}"`);

    const created = await createLessonCommand({
        userId: user._id,
        topic,
        vocabulary,
        modelType,
    });

    const totalTime = performance.now() - startTime;
    console.log(`[Lesson API] Lesson created in ${totalTime.toFixed(2)}ms`);

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
