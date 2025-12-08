import { NextResponse } from "next/server";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    generateMultipleChoiceFromPromptCommand,
    generateMultipleChoiceFromLessonCommand,
    generateSentenceCreationFromPromptCommand,
    generateSentenceCreationFromLessonCommand,
    createExerciseSetCommand,
    getExerciseSetsByUserIdQuery,
    getUserByEmail,
    logger,
} from "@core/index";

export async function POST(req: Request) {
    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await req.json().catch(() => null);
    const {
        source,           // 'from-prompt' | 'from-lesson' | 'manual'
        exerciseType,     // 'multiple_choice' | 'sentence_creation'
        topic,
        exerciseCount,
        lessonId,
        setTitle,
        exercises,
        sourceLesson,
    } = body || {};

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const startTime = performance.now();

    try {
        let exerciseSet;

        if (source === 'from-prompt') {
            // Generate exercises from topic/prompt
            if (!topic || !exerciseCount || !exerciseType) {
                return NextResponse.json(
                    { error: "Topic, exercise count, and exercise type are required" },
                    { status: 400 }
                );
            }

            logger.info(`[Exercise Sets API] Generating ${exerciseType} exercises from prompt for user: ${user.email}`);
            logger.info(`[Exercise Sets API] Topic: "${topic}", Count: ${exerciseCount}`);

            if (exerciseType === 'multiple_choice') {
                exerciseSet = await generateMultipleChoiceFromPromptCommand({
                    userId: user._id,
                    topic,
                    exerciseCount: parseInt(exerciseCount),
                });
            } else if (exerciseType === 'sentence_creation') {
                exerciseSet = await generateSentenceCreationFromPromptCommand({
                    userId: user._id,
                    topic,
                    exerciseCount: parseInt(exerciseCount),
                });
            } else {
                return NextResponse.json(
                    { error: "Invalid exercise type. Must be 'multiple_choice' or 'sentence_creation'" },
                    { status: 400 }
                );
            }
        } else if (source === 'from-lesson') {
            // Generate exercises from lesson
            if (!lessonId || !exerciseCount || !setTitle || !exerciseType) {
                return NextResponse.json(
                    { error: "Lesson ID, set title, exercise count, and exercise type are required" },
                    { status: 400 }
                );
            }

            logger.info(`[Exercise Sets API] Generating ${exerciseType} exercises from lesson for user: ${user.email}`);
            logger.info(`[Exercise Sets API] Lesson ID: ${lessonId}, Count: ${exerciseCount}`);

            if (exerciseType === 'multiple_choice') {
                exerciseSet = await generateMultipleChoiceFromLessonCommand({
                    userId: user._id,
                    lessonId,
                    exerciseCount: parseInt(exerciseCount),
                    setTitle,
                });
            } else if (exerciseType === 'sentence_creation') {
                exerciseSet = await generateSentenceCreationFromLessonCommand({
                    userId: user._id,
                    lessonId,
                    exerciseCount: parseInt(exerciseCount),
                    setTitle,
                });
            } else {
                return NextResponse.json(
                    { error: "Invalid exercise type. Must be 'multiple_choice' or 'sentence_creation'" },
                    { status: 400 }
                );
            }
        } else if (source === 'manual') {
            // Manual exercise set creation
            if (!setTitle || !topic || !exerciseType || !exercises || !Array.isArray(exercises)) {
                return NextResponse.json(
                    { error: "Set title, topic, exercise type, and exercises array are required" },
                    { status: 400 }
                );
            }

            logger.info(`[Exercise Sets API] Creating manual ${exerciseType} exercise set for user: ${user.email}`);

            exerciseSet = await createExerciseSetCommand({
                userId: user._id,
                title: setTitle,
                topic,
                type: exerciseType,
                exercises,
                sourceLesson,
            });
        } else {
            return NextResponse.json(
                { error: "Invalid source. Must be 'from-prompt', 'from-lesson', or 'manual'" },
                { status: 400 }
            );
        }

        const totalTime = performance.now() - startTime;
        logger.info(`[Exercise Sets API] Exercise set created in ${totalTime.toFixed(2)}ms`);

        return NextResponse.json(exerciseSet, { status: 201 });
    } catch (error) {
        logger.error('[Exercise Sets API] Error creating exercise set:', error);
        return NextResponse.json(
            { error: "Failed to create exercise set" },
            { status: 500 }
        );
    }
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

    const exerciseSets = await getExerciseSetsByUserIdQuery(user._id);

    return NextResponse.json({ data: exerciseSets });
}
