import { googleAI } from '@genkit-ai/google-genai';
import { genkit, z } from 'genkit';
import { createFinalPrompt } from './prompt';

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
    userPrompt: z.string().describe('User prompt for the german lesson to be created'),
});

// Define output schema
export const LessonSchema = z.object({
    title: z.string(),
    englishContent: z.string(),
    germanContent: z.string(),
});

// Define a lesson creation flow
export const createLessonFlow = ai.defineFlow(
    {
        name: 'createLessonFlow',
        inputSchema: LessonInputSchema,
        outputSchema: LessonSchema,
    },
    async (input) => {
        // Create a prompt based on the input
        const userPrompt = createFinalPrompt(input.userPrompt);

        // Generate structured lesson data using the same schema
        const { output } = await ai.generate({
            prompt: userPrompt,
            output: { schema: LessonSchema },
        });

        if (!output) throw new Error('Failed to generate lesson');

        return output;
    },
);