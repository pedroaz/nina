import { googleAI } from '@genkit-ai/google-genai';
import { genkit } from 'genkit';
import { z } from 'zod';
import { createFinalPrompt } from './prompt';
import { lessonSchemaZ } from '../entities/lesson';

// Initialize Genkit with the Google AI plugin
const ai = genkit({
    plugins: [googleAI()],
    model: googleAI.model('gemini-2.5-flash', {
        temperature: 0.8,
    }),
    promptDir: './packages/core/llm/prompts',
});

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