import { googleAI } from '@genkit-ai/google-genai';
import { genkit, z } from 'genkit';

// Initialize Genkit with the Google AI plugin
const ai = genkit({
    plugins: [googleAI()],
    model: googleAI.model('gemini-2.5-flash', {
        temperature: 0.8,
    }),
});

// Define input schema
export const LessonInputSchema = z.object({
    prompt: z.string().describe('Prompt for the german lesson to be created'),
});

// Define output schema
export const LessonSchema = z.object({
    title: z.string(),
    content: z.string(),
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
        const prompt = `Create a german summary of the topic writing in english following the topic:${input.prompt}`;

        // Generate structured lesson data using the same schema
        const { output } = await ai.generate({
            prompt,
            output: { schema: LessonSchema },
        });

        if (!output) throw new Error('Failed to generate lesson');

        return output;
    },
);