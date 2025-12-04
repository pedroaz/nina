import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { getUserByEmail } from "@core/index";
import { connectDatabase } from "@core/database/database";
import { LessonModel } from "@core/entities/lesson";
import { ExerciseSetModel } from "@core/entities/exercise-set";
import { FlashCardDeckModel } from "@core/entities/flashcard-deck";
import { MissionChatModel } from "@core/entities/mission-chat";

export async function GET() {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    try {
        await connectDatabase();

        const [lessonsCount, exerciseSetsCount, flashCardDecksCount, missionsCompleted] = await Promise.all([
            LessonModel.countDocuments({ 'studentData.userId': user._id.toString() }),
            ExerciseSetModel.countDocuments({ 'studentData.userId': user._id.toString() }),
            FlashCardDeckModel.countDocuments({ 'studentData.userId': user._id.toString() }),
            MissionChatModel.countDocuments({ userId: user._id.toString(), completed: true }),
        ]);

        return NextResponse.json({
            lessonsCount,
            exerciseSetsCount,
            flashCardDecksCount,
            missionsCompleted,
        });
    } catch (error) {
        console.error('[Stats API] Error fetching stats:', error);
        return NextResponse.json(
            { error: "Failed to fetch stats" },
            { status: 500 }
        );
    }
}
