import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/app/api/auth/[...nextauth]/route';
import {
    getLessonById,
    getPromptMetadataByLessonId,
    getPromptMetadataById,
    getUserByEmail,
} from '@core/index';

export async function GET(
    req: NextRequest,
    context: { params: Promise<{ id: string }> }
) {
    const { id: lessonId } = await context.params;

    if (!lessonId) {
        return NextResponse.json(
            { error: 'Lesson id is required' },
            { status: 400 }
        );
    }

    const session = await getServerSession(authOptions);

    if (!session?.user?.email) {
        return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        return NextResponse.json({ error: 'User not found' }, { status: 404 });
    }

    try {
        // Get the lesson
        const lesson = await getLessonById(lessonId);

        if (!lesson) {
            return NextResponse.json(
                { error: 'Lesson not found' },
                { status: 404 }
            );
        }

        // Verify the lesson belongs to the user
        if (lesson.studentData.userId !== user._id.toString()) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 403 });
        }

        // Get all prompt metadata for this lesson
        const allMetadata = await getPromptMetadataByLessonId(lessonId);

        // Sort by timestamp (oldest first, so lesson creation is first)
        const sortedMetadata = allMetadata.sort(
            (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
        );

        // Calculate totals
        const totals = allMetadata.reduce(
            (acc, metadata) => ({
                totalTokens: acc.totalTokens + metadata.totalTokens,
                totalCost: acc.totalCost + metadata.totalCost,
            }),
            { totalTokens: 0, totalCost: 0 }
        );

        return NextResponse.json({
            operations: sortedMetadata.map((metadata) => ({
                operation: metadata.operation,
                modelUsed: metadata.modelUsed,
                inputTokens: metadata.inputTokens,
                outputTokens: metadata.outputTokens,
                totalTokens: metadata.totalTokens,
                inputCost: metadata.inputCost,
                outputCost: metadata.outputCost,
                totalCost: metadata.totalCost,
                timestamp: metadata.timestamp,
                executionTimeMs: metadata.executionTimeMs,
            })),
            totals: {
                totalTokens: totals.totalTokens,
                totalCost: totals.totalCost,
            },
        });
    } catch (error) {
        console.error('Error fetching lesson metadata:', error);
        return NextResponse.json(
            { error: 'Failed to fetch lesson metadata' },
            { status: 500 }
        );
    }
}
