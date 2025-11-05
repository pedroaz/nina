import { NextRequest, NextResponse } from 'next/server';
import { getServerSession } from 'next-auth';
import { authOptions } from '../auth/[...nextauth]/route';
import { sendChatMessage, type ChatMessage } from '@core/llm/llm';
import type { Lesson } from '@core/entities/lesson';

export async function POST(request: NextRequest) {
    try {
        // Check authentication
        const session = await getServerSession(authOptions);
        if (!session?.user?.email) {
            return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
        }

        // Parse request body
        const body = await request.json();
        const { message, history, lessonContext } = body as {
            message: string;
            history: ChatMessage[];
            lessonContext?: Lesson;
        };

        // Validate input
        if (!message || typeof message !== 'string') {
            return NextResponse.json({ error: 'Message is required' }, { status: 400 });
        }

        if (!Array.isArray(history)) {
            return NextResponse.json({ error: 'History must be an array' }, { status: 400 });
        }

        // Send chat message
        const response = await sendChatMessage(message, history, lessonContext);

        return NextResponse.json({ response }, { status: 200 });
    } catch (error) {
        console.error('Chat API error:', error);
        return NextResponse.json(
            { error: 'Failed to process chat message' },
            { status: 500 }
        );
    }
}
