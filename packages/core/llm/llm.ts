import { genkit } from 'genkit/beta';
import { z } from 'zod';
import { createFinalPrompt } from './prompt';
import { lessonSchemaZ, type Lesson } from '../entities/lesson';
import { openAI } from '@genkit-ai/compat-oai/openai';

const ai = genkit({
    plugins: [openAI({ apiKey: process.env.OPENAI_API_KEY })],
    model: openAI.model('gpt-5-nano'),
    promptDir: './packages/core/llm/prompts',
});

export { ai };

// Define input schema
export const LessonInputSchema = z.object({
    topic: z.string().describe('User topic for the german lesson to be created'),
    vocabulary: z.string().describe('Key vocabulary words to include in the lesson'),
});

// Define output schema
export const LessonSchemaLLM = lessonSchemaZ.omit({
    topic: true,
    vocabulary: true,
    studentData: true,
})

// Define a lesson creation flow
export const createLessonFlow = ai.defineFlow(
    {
        name: 'createLessonFlow',
        inputSchema: LessonInputSchema,
        outputSchema: LessonSchemaLLM,
    },
    async (input) => {

        const userPrompt = createFinalPrompt(input.topic, input.vocabulary);

        const { output } = await ai.generate({
            prompt: userPrompt,
            output: { schema: LessonSchemaLLM },
        });

        if (!output) throw new Error('Failed to generate lesson');

        return output;
    },
);

// Chat functionality for Nina assistant
export interface ChatMessage {
    role: 'user' | 'model';
    content: string;
}

function formatLessonContext(lesson: Lesson): string {
    const parts = [
        `Topic: ${lesson.topic}`,
        lesson.vocabulary ? `Vocabulary: ${lesson.vocabulary}` : '',
        `Title: ${lesson.title.base || ''} / ${lesson.title.german || ''}`,
        `Summary: ${lesson.quickSummary.base || ''}`,
        lesson.quickExamples.length > 0 ? `Examples:\n${lesson.quickExamples.map(ex => `- ${ex.base || ''} / ${ex.german || ''}`).join('\n')}` : '',
        `Full Explanation: ${lesson.fullExplanation.base || ''}`,
    ];
    return parts.filter(Boolean).join('\n\n');
}

export async function sendChatMessage(
    userMessage: string,
    history: ChatMessage[],
    lessonContext?: Lesson
): Promise<string> {
    const systemPrompt = lessonContext
        ? `You are Nina, a friendly and helpful German learning assistant. You help students understand German grammar, vocabulary, and usage.

The student is currently studying the following lesson:

${formatLessonContext(lessonContext)}

Use this lesson context to provide relevant examples and explanations. Reference specific parts of the lesson when helpful.`
        : `You are Nina, a friendly and helpful German learning assistant. You help students understand German grammar, vocabulary, and usage in a clear and encouraging way.`;

    // Build conversation context from history
    let conversationContext = '';
    if (history.length > 0) {
        conversationContext = '\n\nPrevious conversation:\n';
        for (const msg of history) {
            const speaker = msg.role === 'user' ? 'Student' : 'Nina';
            conversationContext += `${speaker}: ${msg.content}\n`;
        }
        conversationContext += '\n';
    }

    // Create full prompt with history context
    const fullPrompt = `${systemPrompt}${conversationContext}

Student: ${userMessage}

Nina:`;

    // Generate response in a single call
    const { text } = await ai.generate({
        prompt: fullPrompt,
    });

    return text;
}