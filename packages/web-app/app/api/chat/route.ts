import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../auth/[...nextauth]/route';
import { sendChatMessage, type ChatMessage, getUserByEmail, savePromptMetadataCommand } from '@core/index';
import type { Lesson } from '@core/entities/lesson';
import logger from "@/lib/logger"


export async function POST(request: NextRequest) {
    const startTime = performance.now();
    logger.info('[Chat API] Request received');

    try {
        // Check authentication
        const authStart = performance.now();
        const session = await getServerSession(authOptions);
        const authEnd = performance.now();
        logger.info(`[Chat API] Authentication check: ${(authEnd - authStart).toFixed(2)}ms`);

        if (!session?.user?.email) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        const user = await getUserByEmail(session.user.email);
        if (!user) {
            return NextResponse.json({ error: 'User not found' }, { status: 404 });
        }

        // Parse request body
        const parseStart = performance.now();
        const body = await request.json();
        const { message, history, lessonContext } = body as {
            message: string;
            history: ChatMessage[];
            lessonContext?: Lesson;
        };
        const parseEnd = performance.now();
        logger.info(`[Chat API] Body parsing: ${(parseEnd - parseStart).toFixed(2)}ms`);
        logger.info(`[Chat API] Message length: ${message.length} chars`);
        logger.info(`[Chat API] History length: ${history.length} messages`);
        logger.info(`[Chat API] Has lesson context: ${!!lessonContext}`);

        // Validate input
        if (!message || typeof message !== 'string') {
            return NextResponse.json({ error: 'Message is required' }, { status: 400 });
        }

        if (!Array.isArray(history)) {
            return NextResponse.json({ error: 'History must be an array' }, { status: 400 });
        }

        // Send chat message
        logger.info('[Chat API] Sending message to LLM...');
        const llmStart = performance.now();
        const { message: response, usage } = await sendChatMessage(message, history, lessonContext);
        const llmEnd = performance.now();
        logger.info(`[Chat API] LLM response time: ${(llmEnd - llmStart).toFixed(2)}ms`);
        logger.info(`[Chat API] Response length: ${response.length} chars`);

        // Save prompt metadata for chat
        await savePromptMetadataCommand({
            lessonId: lessonContext?._id,
            operation: 'chat',
            modelUsed: usage.modelUsed as 'gpt-5-nano' | 'gpt-4o-mini',
            inputTokens: usage.inputTokens,
            outputTokens: usage.outputTokens,
            totalTokens: usage.totalTokens,
            userId: user._id.toString(),
            executionTimeMs: usage.executionTimeMs,
            finishReason: usage.finishReason,
        });

        const totalTime = performance.now() - startTime;
        logger.info(`[Chat API] Total request time: ${totalTime.toFixed(2)}ms`);

        return NextResponse.json({ response }, { status: 200 });
    } catch (error) {
        const totalTime = performance.now() - startTime;
        logger.error(`[Chat API] Error after ${totalTime.toFixed(2)}ms: ${String(error)}`);
        return NextResponse.json(
            { error: 'Failed to process chat message' },
            { status: 500 }
        );
    }
}
