import { genkit } from 'genkit/beta';
import { z } from 'zod';
import { createFinalPrompt } from './prompt';
import { lessonSchemaZ, type Lesson } from '../entities/lesson';
import { dualLanguageSchemaZ } from '../entities/base';
import { flashCardSchemaZ } from '../entities/flashcard-deck';
import { studentLevelSchemaZ } from '../entities/student';
import { openAI } from '@genkit-ai/compat-oai/openai';
import { MODEL_CATEGORIES, getModelName, getModelConfig } from './model-config';
import { createFlashCardFromPromptInstructions, createFlashCardFromLessonInstructions } from './flashcard-prompt';

/*
gpt-4.5
gpt-4.5-preview
gpt-4o
gpt-4o-2024-05-13
o1
o3
o3-mini
o4-mini
gpt-4o-mini
gpt-4o-mini-2024-07-18
gpt-4-turbo
gpt-4-turbo-2024-04-09
gpt-4-turbo-preview
gpt-4-0125-preview
gpt-4-1106-preview
gpt-4-vision
gpt-4-vision-preview
gpt-4-1106-vision-preview
gpt-4
gpt-4-0613
gpt-4-32k
gpt-4-32k-0613
gpt-3.5-turbo
gpt-3.5-turbo-0125
gpt-3.5-turbo-1106
gpt-5
gpt-5-mini
gpt-5-nano
gpt-5-chat-latest
*/

// AI instance for lesson creation - uses DETAILED model category
const ai = genkit({
    plugins: [openAI({ apiKey: process.env.OPENAI_API_KEY })],
    model: openAI.model(getModelName(MODEL_CATEGORIES.DETAILED)),
    promptDir: './packages/core/llm/prompts',
});

// AI instance for chat - uses FAST model category
const chatAi = genkit({
    plugins: [openAI({ apiKey: process.env.OPENAI_API_KEY })],
    model: openAI.model(getModelName(MODEL_CATEGORIES.FAST)),
    promptDir: './packages/core/llm/prompts',
});

export { ai };
export { MODEL_CATEGORIES, getModelConfig } from './model-config';

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
        const modelConfig = getModelConfig(MODEL_CATEGORIES.DETAILED);
        const startTime = performance.now();

        console.log(`[Lesson Creation] Starting lesson generation`);
        console.log(`[Lesson Creation] Using ${modelConfig.displayName}`);
        console.log(`[Lesson Creation] Topic: "${input.topic}"`);
        console.log(`[Lesson Creation] Vocabulary: "${input.vocabulary}"`);

        const userPrompt = createFinalPrompt(input.topic, input.vocabulary);

        const generateStart = performance.now();
        const { output } = await ai.generate({
            prompt: userPrompt,
            output: { schema: LessonSchemaLLM },
        });
        const generateEnd = performance.now();

        console.log(`[Lesson Creation] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);

        if (!output) throw new Error('Failed to generate lesson');

        const totalTime = performance.now() - startTime;
        console.log(`[Lesson Creation] Total time: ${totalTime.toFixed(2)}ms`);
        console.log(`[Lesson Creation] Lesson created successfully`);

        return output;
    },
);

// Define input schema for extra sections
export const ExtraSectionInputSchema = z.object({
    request: z.string().describe('User request for additional content'),
    lessonContext: z.object({
        topic: z.string(),
        vocabulary: z.string().optional(),
        title: dualLanguageSchemaZ,
        quickSummary: dualLanguageSchemaZ,
    }),
});

// Define a flow for appending extra sections
export const appendExtraSectionFlow = chatAi.defineFlow(
    {
        name: 'appendExtraSectionFlow',
        inputSchema: ExtraSectionInputSchema,
        outputSchema: dualLanguageSchemaZ,
    },
    async (input) => {
        const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
        const startTime = performance.now();

        console.log(`[Extra Section] Starting extra section generation`);
        console.log(`[Extra Section] Using ${modelConfig.displayName}`);
        console.log(`[Extra Section] Request: "${input.request}"`);
        console.log(`[Extra Section] Topic: "${input.lessonContext.topic}"`);

        const prompt = `You are Nina, a German learning assistant. A student is studying a lesson about "${input.lessonContext.topic}" ${input.lessonContext.vocabulary ? `with vocabulary: ${input.lessonContext.vocabulary}` : ''}.

Lesson Title: ${input.lessonContext.title.base} / ${input.lessonContext.title.target}
Summary: ${input.lessonContext.quickSummary.base}

The student has requested: "${input.request}"

Generate educational content that addresses the student's request. Provide:

1. A complete response in English (this will be the "base" field)
2. The same content translated to German (this will be the "german" field)

Use markdown formatting for better readability. If they asked for examples, provide all examples in a well-formatted list. Keep it educational and engaging.

Important: Return a JSON object with exactly two string fields: "base" (English content) and "german" (German content). Do not return the schema structure itself.`;

        const generateStart = performance.now();
        const { output } = await chatAi.generate({
            prompt: prompt,
            output: { schema: dualLanguageSchemaZ },
        });
        const generateEnd = performance.now();

        console.log(`[Extra Section] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);

        if (!output) throw new Error('Failed to generate extra section');

        const totalTime = performance.now() - startTime;
        console.log(`[Extra Section] Total time: ${totalTime.toFixed(2)}ms`);
        console.log(`[Extra Section] Extra section created successfully`);

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
        `Title: ${lesson.title.base || ''} / ${lesson.title.target || ''}`,
        `Summary: ${lesson.quickSummary.base || ''}`,
        lesson.quickExamples.length > 0 ? `Examples:\n${lesson.quickExamples.map(ex => `- ${ex.base || ''} / ${ex.target || ''}`).join('\n')}` : '',
        `Full Explanation: ${lesson.fullExplanation.base || ''}`,
    ];
    return parts.filter(Boolean).join('\n\n');
}

export async function sendChatMessage(
    userMessage: string,
    history: ChatMessage[],
    lessonContext?: Lesson
): Promise<string> {
    const startTime = performance.now();
    console.log('[LLM] Building prompt...');

    const promptStart = performance.now();
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

    const promptEnd = performance.now();
    console.log(`[LLM] Prompt built in: ${(promptEnd - promptStart).toFixed(2)}ms`);
    console.log(`[LLM] Prompt length: ${fullPrompt.length} chars`);

    // Generate response in a single call using fast chat model
    console.log('[LLM] Calling AI model (gpt-4o-mini)...');
    const generateStart = performance.now();
    const { text } = await chatAi.generate({
        prompt: fullPrompt,
    });
    const generateEnd = performance.now();
    console.log(`[LLM] AI generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);

    const totalTime = performance.now() - startTime;
    console.log(`[LLM] Total LLM function time: ${totalTime.toFixed(2)}ms`);

    return text;
}

// Flash Card Generation Flows

// Schema for generating flash cards from prompt
export const FlashCardFromPromptInputSchema = z.object({
    topic: z.string().describe('Topic for the flash cards'),
    cardCount: z.number().describe('Number of flash cards to generate'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
});

export const FlashCardFromPromptOutputSchema = z.object({
    title: z.string().describe('Deck title'),
    cards: z.array(flashCardSchemaZ.omit({ _id: true })).describe('Array of flash cards'),
});

// Flow for generating flash cards from a topic/prompt
export const generateFlashCardsFromPromptFlow = chatAi.defineFlow(
    {
        name: 'generateFlashCardsFromPromptFlow',
        inputSchema: FlashCardFromPromptInputSchema,
        outputSchema: FlashCardFromPromptOutputSchema,
    },
    async (input) => {
        const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
        const startTime = performance.now();

        console.log(`[Flash Cards] Starting flash card generation from prompt`);
        console.log(`[Flash Cards] Using ${modelConfig.displayName}`);
        console.log(`[Flash Cards] Topic: "${input.topic}"`);
        console.log(`[Flash Cards] Card count: ${input.cardCount}`);
        console.log(`[Flash Cards] Student level: ${input.studentLevel}`);

        const prompt = createFlashCardFromPromptInstructions(
            input.topic,
            input.cardCount,
            input.studentLevel
        );

        const generateStart = performance.now();
        const { output } = await chatAi.generate({
            prompt: prompt,
            output: { schema: FlashCardFromPromptOutputSchema },
        });
        const generateEnd = performance.now();

        console.log(`[Flash Cards] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);

        if (!output) throw new Error('Failed to generate flash cards from prompt');

        const totalTime = performance.now() - startTime;
        console.log(`[Flash Cards] Total time: ${totalTime.toFixed(2)}ms`);
        console.log(`[Flash Cards] Generated ${output.cards.length} cards`);

        return output;
    },
);

// Schema for generating flash cards from lesson
export const FlashCardFromLessonInputSchema = z.object({
    lesson: lessonSchemaZ.describe('The lesson to extract flash cards from'),
    cardCount: z.number().describe('Number of flash cards to generate'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
});

export const FlashCardFromLessonOutputSchema = z.object({
    cards: z.array(flashCardSchemaZ.omit({ _id: true })).describe('Array of flash cards'),
});

// Flow for generating flash cards from a lesson
export const generateFlashCardsFromLessonFlow = chatAi.defineFlow(
    {
        name: 'generateFlashCardsFromLessonFlow',
        inputSchema: FlashCardFromLessonInputSchema,
        outputSchema: FlashCardFromLessonOutputSchema,
    },
    async (input) => {
        const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
        const startTime = performance.now();

        console.log(`[Flash Cards] Starting flash card generation from lesson`);
        console.log(`[Flash Cards] Using ${modelConfig.displayName}`);
        console.log(`[Flash Cards] Lesson topic: "${input.lesson.topic}"`);
        console.log(`[Flash Cards] Card count: ${input.cardCount}`);
        console.log(`[Flash Cards] Student level: ${input.studentLevel}`);

        const prompt = createFlashCardFromLessonInstructions(
            input.lesson.topic,
            input.lesson.title.base,
            input.lesson.quickSummary.base,
            input.lesson.fullExplanation.base,
            input.cardCount,
            input.studentLevel
        );

        const generateStart = performance.now();
        const { output } = await chatAi.generate({
            prompt: prompt,
            output: { schema: FlashCardFromLessonOutputSchema },
        });
        const generateEnd = performance.now();

        console.log(`[Flash Cards] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);

        if (!output) throw new Error('Failed to generate flash cards from lesson');

        const totalTime = performance.now() - startTime;
        console.log(`[Flash Cards] Total time: ${totalTime.toFixed(2)}ms`);
        console.log(`[Flash Cards] Generated ${output.cards.length} cards`);

        return output;
    },
);