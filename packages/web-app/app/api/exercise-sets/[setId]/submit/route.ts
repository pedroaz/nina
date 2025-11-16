import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    submitExerciseAnswerCommand,
    getUserByEmail,
} from "@core/index";

export async function POST(
    req: Request,
    { params }: { params: Promise<{ setId: string }> }
) {
    const { setId } = await params;
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await req.json().catch(() => null);
    const { exerciseId, userAnswer } = body || {};

    if (!exerciseId || userAnswer === undefined) {
        return NextResponse.json(
            { error: "Exercise ID and user answer are required" },
            { status: 400 }
        );
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    try {
        const result = await submitExerciseAnswerCommand({
            userId: user._id,
            exerciseSetId: setId,
            exerciseId,
            userAnswer: String(userAnswer),
        });

        return NextResponse.json(result);
    } catch (error) {
        console.error('[Exercise Submit API] Error submitting answer:', error);
        return NextResponse.json(
            { error: "Failed to submit exercise answer" },
            { status: 500 }
        );
    }
}
