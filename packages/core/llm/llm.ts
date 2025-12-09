import { genkit } from 'genkit/beta';
import { z } from 'zod';
import logger from '../logger';
import { createFinalPrompt } from './prompt';
import { lessonSchemaZ, type Lesson } from '../entities/lesson';
import { dualLanguageSchemaZ } from '../entities/base';
import { flashCardSchemaZ } from '../entities/flashcard-deck';
import { studentLevelSchemaZ } from '../entities/student';
import { multipleChoiceExerciseSchemaZ, sentenceCreationExerciseSchemaZ } from '../entities/exercise-set';
import { openAI } from '@genkit-ai/compat-oai/openai';
import { MODEL_CATEGORIES, getModelName, getModelConfig } from './model-config';
import { createFlashCardFromPromptInstructions, createFlashCardFromLessonInstructions } from './flashcard-prompt';
import {
    createMultipleChoiceFromPromptInstructions,
    createMultipleChoiceFromLessonInstructions,
    createSentenceCreationFromPromptInstructions,
    createSentenceCreationFromLessonInstructions,
    judgeSentenceInstructions,
} from './exercise-prompt';

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
export const chatAi = genkit({
    plugins: [openAI({ apiKey: process.env.OPENAI_API_KEY })],
    model: openAI.model(getModelName(MODEL_CATEGORIES.FAST)),
    promptDir: './packages/core/llm/prompts',
});

export { ai };
export { MODEL_CATEGORIES, getModelConfig } from './model-config';

// Define input schema
export const LessonInputSchema = z.object({
    topic: z.string().describe('User topic for the lesson to be created'),
    vocabulary: z.string().describe('Key vocabulary words to include in the lesson'),
    baseLanguage: z.string().describe('Base language (user native language)'),
    targetLanguage: z.string().describe('Target language (language being learned)'),
    modelType: z.enum(['fast', 'detailed']).optional().describe('Model type to use (defaults to detailed)'),
    focus: z.enum(['vocabulary', 'grammar']).optional().describe('Focus of the lesson (vocabulary or grammar)'),
    image: z.string().optional().describe('Base64 encoded image to generate lesson from'),
});

// Define output schema
export const LessonSchemaLLM = lessonSchemaZ.omit({
    topic: true,
    vocabulary: true,
    studentData: true,
    modelUsed: true,
    creationPromptMetadataId: true,
})

// Usage metadata type
export interface UsageMetadata {
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
    modelUsed: string;
    executionTimeMs: number;
    finishReason?: string;
}

// Define a lesson creation flow - returns both lesson and usage metadata
export const createLessonFlow = async (
    input: z.infer<typeof LessonInputSchema>
): Promise<{ lesson: z.infer<typeof LessonSchemaLLM>; usage: UsageMetadata }> => {
    const modelCategory = input.modelType || MODEL_CATEGORIES.DETAILED;
    const modelConfig = getModelConfig(modelCategory as any);
    const aiInstance = modelCategory === MODEL_CATEGORIES.FAST ? chatAi : ai;
    const startTime = performance.now();

    logger.info(`[Lesson Creation] Starting lesson generation`);
    logger.info(`[Lesson Creation] Using ${modelConfig.displayName}`);
    logger.info(`[Lesson Creation] Topic: "${input.topic}"`);
    logger.info(`[Lesson Creation] Vocabulary: "${input.vocabulary}"`);
    logger.info(`[Lesson Creation] Base language: "${input.baseLanguage}"`);
    logger.info(`[Lesson Creation] Target language: "${input.targetLanguage}"`);
    logger.info(`[Lesson Creation] Focus: "${input.focus || 'general'}"`);

    const userPrompt = createFinalPrompt(input.topic, input.vocabulary, input.baseLanguage, input.targetLanguage, input.focus);

    let promptInput: any = userPrompt;
    if (input.image) {
        logger.info(`[Lesson Creation] Image provided, using vision capabilities`);
        promptInput = [
            { text: userPrompt },
            { media: { url: input.image } }
        ];
    }

    const generateStart = performance.now();
    const response = await aiInstance.generate({
        prompt: promptInput,
        output: { schema: LessonSchemaLLM },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Lesson Creation] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Lesson Creation] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Lesson Creation] Output tokens: ${usage?.outputTokens || 0}`);
    logger.info(`[Lesson Creation] Total tokens: ${usage?.totalTokens || 0}`);

    if (!output) throw new Error('Failed to generate lesson');

    const totalTime = performance.now() - startTime;
    logger.info(`[Lesson Creation] Total time: ${totalTime.toFixed(2)}ms`);
    logger.info(`[Lesson Creation] Lesson created successfully`);

    return {
        lesson: output,
        usage: {
            inputTokens: usage?.inputTokens || 0,
            outputTokens: usage?.outputTokens || 0,
            totalTokens: usage?.totalTokens || 0,
            modelUsed: modelConfig.name,
            executionTimeMs: totalTime,
            finishReason: finishReason || undefined,
        },
    };
};

// Define input schema for extra sections
export const ExtraSectionInputSchema = z.object({
    request: z.string().describe('User request for additional content'),
    lessonContext: z.object({
        topic: z.string(),
        vocabulary: z.string().optional(),
        title: dualLanguageSchemaZ,
        quickSummary: dualLanguageSchemaZ,
        baseLanguage: z.string(),
        targetLanguage: z.string(),
    }),
});

// Define a flow for appending extra sections - returns both section and usage metadata
export const appendExtraSectionFlow = async (
    input: z.infer<typeof ExtraSectionInputSchema>
): Promise<{ section: z.infer<typeof dualLanguageSchemaZ>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    const startTime = performance.now();

    logger.info(`[Extra Section] Starting extra section generation`);
    logger.info(`[Extra Section] Using ${modelConfig.displayName}`);
    logger.info(`[Extra Section] Request: "${input.request}"`);
    logger.info(`[Extra Section] Topic: "${input.lessonContext.topic}"`);

    const prompt = `You are Nina, a ${input.lessonContext.targetLanguage} learning assistant. A student is studying a lesson about "${input.lessonContext.topic}" ${input.lessonContext.vocabulary ? `with vocabulary: ${input.lessonContext.vocabulary}` : ''}.

Lesson Title: ${input.lessonContext.title.base} / ${input.lessonContext.title.target}
Summary: ${input.lessonContext.quickSummary.base}

The student has requested: "${input.request}"

Generate educational content that addresses the student's request. Provide:

1. A complete response in ${input.lessonContext.baseLanguage} (this will be the "base" field)
2. The same content translated to ${input.lessonContext.targetLanguage} (this will be the "target" field)

Use markdown formatting for better readability. If they asked for examples, provide all examples in a well-formatted list. Keep it educational and engaging.

Important: Return a JSON object with exactly two string fields: "base" (${input.lessonContext.baseLanguage} content) and "target" (${input.lessonContext.targetLanguage} content). Do not return the schema structure itself.`;

    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: prompt,
        output: { schema: dualLanguageSchemaZ },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Extra Section] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Extra Section] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Extra Section] Output tokens: ${usage?.outputTokens || 0}`);

    if (!output) throw new Error('Failed to generate extra section');

    const totalTime = performance.now() - startTime;
    logger.info(`[Extra Section] Total time: ${totalTime.toFixed(2)}ms`);
    logger.info(`[Extra Section] Extra section created successfully`);

    return {
        section: output,
        usage: {
            inputTokens: usage?.inputTokens || 0,
            outputTokens: usage?.outputTokens || 0,
            totalTokens: usage?.totalTokens || 0,
            modelUsed: modelConfig.name,
            executionTimeMs: totalTime,
            finishReason: finishReason || undefined,
        },
    };
};

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
    lessonContext?: Lesson,
    targetLanguage: string = 'German'
): Promise<{ message: string; usage: UsageMetadata }> {
    const startTime = performance.now();
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    logger.info('[LLM] Building prompt...');

    const promptStart = performance.now();
    const systemPrompt = lessonContext
        ? `You are Nina, a friendly and helpful ${targetLanguage} learning assistant. You help students understand ${targetLanguage} grammar, vocabulary, and usage.

The student is currently studying the following lesson:

${formatLessonContext(lessonContext)}

Use this lesson context to provide relevant examples and explanations. Reference specific parts of the lesson when helpful.`
        : `You are Nina, a friendly and helpful ${targetLanguage} learning assistant. You help students understand ${targetLanguage} grammar, vocabulary, and usage in a clear and encouraging way.`;

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
    logger.info(`[LLM] Prompt built in: ${(promptEnd - promptStart).toFixed(2)}ms`);
    logger.info(`[LLM] Prompt length: ${fullPrompt.length} chars`);

    // Generate response in a single call using fast chat model
    logger.info('[LLM] Calling AI model (gpt-4o-mini)...');
    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: fullPrompt,
    });
    const { text, usage, finishReason } = response;
    const generateEnd = performance.now();
    logger.info(`[LLM] AI generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[LLM] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[LLM] Output tokens: ${usage?.outputTokens || 0}`);

    const totalTime = performance.now() - startTime;
    logger.info(`[LLM] Total LLM function time: ${totalTime.toFixed(2)}ms`);

    return {
        message: text,
        usage: {
            inputTokens: usage?.inputTokens || 0,
            outputTokens: usage?.outputTokens || 0,
            totalTokens: usage?.totalTokens || 0,
            modelUsed: modelConfig.name,
            executionTimeMs: totalTime,
            finishReason: finishReason || undefined,
        },
    };
}

// Flash Card Generation Flows

// Schema for generating flash cards from prompt
export const FlashCardFromPromptInputSchema = z.object({
    topic: z.string().describe('Topic for the flash cards'),
    cardCount: z.number().describe('Number of flash cards to generate'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
    baseLanguage: z.string().describe('Base language (user native language)'),
    targetLanguage: z.string().describe('Target language (language being learned)'),
});

export const FlashCardFromPromptOutputSchema = z.object({
    title: z.string().describe('Deck title'),
    cards: z.array(flashCardSchemaZ.omit({ _id: true })).describe('Array of flash cards'),
});

// Flow for generating flash cards from a topic/prompt - returns cards and usage metadata
export const generateFlashCardsFromPromptFlow = async (
    input: z.infer<typeof FlashCardFromPromptInputSchema>
): Promise<{ output: z.infer<typeof FlashCardFromPromptOutputSchema>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    const startTime = performance.now();

    logger.info(`[Flash Cards] Starting flash card generation from prompt`);
    logger.info(`[Flash Cards] Using ${modelConfig.displayName}`);
    logger.info(`[Flash Cards] Topic: "${input.topic}"`);
    logger.info(`[Flash Cards] Card count: ${input.cardCount}`);
    logger.info(`[Flash Cards] Student level: ${input.studentLevel}`);
    logger.info(`[Flash Cards] Base language: "${input.baseLanguage}"`);
    logger.info(`[Flash Cards] Target language: "${input.targetLanguage}"`);

    const prompt = createFlashCardFromPromptInstructions(
        input.topic,
        input.cardCount,
        input.studentLevel,
        input.baseLanguage,
        input.targetLanguage
    );

    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: prompt,
        output: { schema: FlashCardFromPromptOutputSchema },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Flash Cards] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Flash Cards] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Flash Cards] Output tokens: ${usage?.outputTokens || 0}`);

    if (!output) throw new Error('Failed to generate flash cards from prompt');

    const totalTime = performance.now() - startTime;
    logger.info(`[Flash Cards] Total time: ${totalTime.toFixed(2)}ms`);
    logger.info(`[Flash Cards] Generated ${output.cards.length} cards`);

    return {
        output,
        usage: {
            inputTokens: usage?.inputTokens || 0,
            outputTokens: usage?.outputTokens || 0,
            totalTokens: usage?.totalTokens || 0,
            modelUsed: modelConfig.name,
            executionTimeMs: totalTime,
            finishReason: finishReason || undefined,
        },
    };
};

// Schema for generating flash cards from lesson
export const FlashCardFromLessonInputSchema = z.object({
    lesson: lessonSchemaZ.describe('The lesson to extract flash cards from'),
    cardCount: z.number().describe('Number of flash cards to generate'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
    baseLanguage: z.string().describe('Base language (user native language)'),
    targetLanguage: z.string().describe('Target language (language being learned)'),
});

export const FlashCardFromLessonOutputSchema = z.object({
    cards: z.array(flashCardSchemaZ.omit({ _id: true })).describe('Array of flash cards'),
});

// Flow for generating flash cards from a lesson - returns cards and usage metadata
export const generateFlashCardsFromLessonFlow = async (
    input: z.infer<typeof FlashCardFromLessonInputSchema>
): Promise<{ output: z.infer<typeof FlashCardFromLessonOutputSchema>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    const startTime = performance.now();

    logger.info(`[Flash Cards] Starting flash card generation from lesson`);
    logger.info(`[Flash Cards] Using ${modelConfig.displayName}`);
    logger.info(`[Flash Cards] Lesson topic: "${input.lesson.topic}"`);
    logger.info(`[Flash Cards] Card count: ${input.cardCount}`);
    logger.info(`[Flash Cards] Student level: ${input.studentLevel}`);
    logger.info(`[Flash Cards] Base language: "${input.baseLanguage}"`);
    logger.info(`[Flash Cards] Target language: "${input.targetLanguage}"`);

    const prompt = createFlashCardFromLessonInstructions(
        input.lesson.topic,
        input.lesson.title.base,
        input.lesson.quickSummary.base,
        input.lesson.fullExplanation.base,
        input.cardCount,
        input.studentLevel,
        input.baseLanguage,
        input.targetLanguage
    );

    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: prompt,
        output: { schema: FlashCardFromLessonOutputSchema },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Flash Cards] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Flash Cards] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Flash Cards] Output tokens: ${usage?.outputTokens || 0}`);

    if (!output) throw new Error('Failed to generate flash cards from lesson');

    const totalTime = performance.now() - startTime;
    logger.info(`[Flash Cards] Total time: ${totalTime.toFixed(2)}ms`);
    logger.info(`[Flash Cards] Generated ${output.cards.length} cards`);

    return {
        output,
        usage: {
            inputTokens: usage?.inputTokens || 0,
            outputTokens: usage?.outputTokens || 0,
            totalTokens: usage?.totalTokens || 0,
            modelUsed: modelConfig.name,
            executionTimeMs: totalTime,
            finishReason: finishReason || undefined,
        },
    };
};

// Exercise Generation Flows

// Schema for generating multiple choice exercises from prompt
export const MultipleChoiceFromPromptInputSchema = z.object({
    topic: z.string().describe('Topic for the exercises'),
    exerciseCount: z.number().describe('Number of exercises to generate'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
    baseLanguage: z.string().describe('Base language (user native language)'),
    targetLanguage: z.string().describe('Target language (language being learned)'),
});

export const MultipleChoiceFromPromptOutputSchema = z.object({
    title: z.string().describe('Exercise set title'),
    exercises: z.array(multipleChoiceExerciseSchemaZ.omit({ _id: true })).describe('Array of multiple choice exercises'),
});

// Flow for generating multiple choice exercises from a topic/prompt
export const generateMultipleChoiceFromPromptFlow = async (
    input: z.infer<typeof MultipleChoiceFromPromptInputSchema>
): Promise<{ output: z.infer<typeof MultipleChoiceFromPromptOutputSchema>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    const startTime = performance.now();

    logger.info(`[Exercises MC] Starting multiple choice generation from prompt`);
    logger.info(`[Exercises MC] Using ${modelConfig.displayName}`);
    logger.info(`[Exercises MC] Topic: "${input.topic}"`);
    logger.info(`[Exercises MC] Exercise count: ${input.exerciseCount}`);
    logger.info(`[Exercises MC] Student level: ${input.studentLevel}`);

    const prompt = createMultipleChoiceFromPromptInstructions(
        input.topic,
        input.exerciseCount,
        input.studentLevel,
        input.baseLanguage,
        input.targetLanguage
    );

    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: prompt,
        output: { schema: MultipleChoiceFromPromptOutputSchema },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Exercises MC] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Exercises MC] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Exercises MC] Output tokens: ${usage?.outputTokens || 0}`);

    if (!output) throw new Error('Failed to generate multiple choice exercises from prompt');

    const totalTime = performance.now() - startTime;
    logger.info(`[Exercises MC] Total time: ${totalTime.toFixed(2)}ms`);
    logger.info(`[Exercises MC] Generated ${output.exercises.length} exercises`);

    return {
        output,
        usage: {
            inputTokens: usage?.inputTokens || 0,
            outputTokens: usage?.outputTokens || 0,
            totalTokens: usage?.totalTokens || 0,
            modelUsed: modelConfig.name,
            executionTimeMs: totalTime,
            finishReason: finishReason || undefined,
        },
    };
};

// Schema for generating multiple choice exercises from lesson
export const MultipleChoiceFromLessonInputSchema = z.object({
    lesson: lessonSchemaZ.describe('The lesson to create exercises from'),
    exerciseCount: z.number().describe('Number of exercises to generate'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
    baseLanguage: z.string().describe('Base language (user native language)'),
    targetLanguage: z.string().describe('Target language (language being learned)'),
});

export const MultipleChoiceFromLessonOutputSchema = z.object({
    exercises: z.array(multipleChoiceExerciseSchemaZ.omit({ _id: true })).describe('Array of multiple choice exercises'),
});

// Flow for generating multiple choice exercises from a lesson
export const generateMultipleChoiceFromLessonFlow = async (
    input: z.infer<typeof MultipleChoiceFromLessonInputSchema>
): Promise<{ output: z.infer<typeof MultipleChoiceFromLessonOutputSchema>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    const startTime = performance.now();

    logger.info(`[Exercises MC] Starting multiple choice generation from lesson`);
    logger.info(`[Exercises MC] Using ${modelConfig.displayName}`);
    logger.info(`[Exercises MC] Lesson topic: "${input.lesson.topic}"`);
    logger.info(`[Exercises MC] Exercise count: ${input.exerciseCount}`);

    const prompt = createMultipleChoiceFromLessonInstructions(
        input.lesson.topic,
        input.lesson.title.base,
        input.lesson.quickSummary.base,
        input.lesson.fullExplanation.base,
        input.exerciseCount,
        input.studentLevel,
        input.baseLanguage,
        input.targetLanguage
    );

    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: prompt,
        output: { schema: MultipleChoiceFromLessonOutputSchema },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Exercises MC] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Exercises MC] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Exercises MC] Output tokens: ${usage?.outputTokens || 0}`);

    if (!output) throw new Error('Failed to generate multiple choice exercises from lesson');

    const totalTime = performance.now() - startTime;
    logger.info(`[Exercises MC] Total time: ${totalTime.toFixed(2)}ms`);
    logger.info(`[Exercises MC] Generated ${output.exercises.length} exercises`);

    return {
        output,
        usage: {
            inputTokens: usage?.inputTokens || 0,
            outputTokens: usage?.outputTokens || 0,
            totalTokens: usage?.totalTokens || 0,
            modelUsed: modelConfig.name,
            executionTimeMs: totalTime,
            finishReason: finishReason || undefined,
        },
    };
};

// Schema for generating sentence creation exercises from prompt
export const SentenceCreationFromPromptInputSchema = z.object({
    topic: z.string().describe('Topic for the exercises'),
    exerciseCount: z.number().describe('Number of exercises to generate'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
    baseLanguage: z.string().describe('Base language (user native language)'),
    targetLanguage: z.string().describe('Target language (language being learned)'),
});

export const SentenceCreationFromPromptOutputSchema = z.object({
    title: z.string().describe('Exercise set title'),
    exercises: z.array(sentenceCreationExerciseSchemaZ.omit({ _id: true })).describe('Array of sentence creation exercises'),
});

// Flow for generating sentence creation exercises from a topic/prompt
export const generateSentenceCreationFromPromptFlow = async (
    input: z.infer<typeof SentenceCreationFromPromptInputSchema>
): Promise<{ output: z.infer<typeof SentenceCreationFromPromptOutputSchema>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    const startTime = performance.now();

    logger.info(`[Exercises SC] Starting sentence creation generation from prompt`);
    logger.info(`[Exercises SC] Using ${modelConfig.displayName}`);
    logger.info(`[Exercises SC] Topic: "${input.topic}"`);
    logger.info(`[Exercises SC] Exercise count: ${input.exerciseCount}`);
    logger.info(`[Exercises SC] Student level: ${input.studentLevel}`);

    const prompt = createSentenceCreationFromPromptInstructions(
        input.topic,
        input.exerciseCount,
        input.studentLevel,
        input.baseLanguage,
        input.targetLanguage
    );

    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: prompt,
        output: { schema: SentenceCreationFromPromptOutputSchema },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Exercises SC] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Exercises SC] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Exercises SC] Output tokens: ${usage?.outputTokens || 0}`);

    if (!output) throw new Error('Failed to generate sentence creation exercises from prompt');

    const totalTime = performance.now() - startTime;
    logger.info(`[Exercises SC] Total time: ${totalTime.toFixed(2)}ms`);
    logger.info(`[Exercises SC] Generated ${output.exercises.length} exercises`);

    return {
        output,
        usage: {
            inputTokens: usage?.inputTokens || 0,
            outputTokens: usage?.outputTokens || 0,
            totalTokens: usage?.totalTokens || 0,
            modelUsed: modelConfig.name,
            executionTimeMs: totalTime,
            finishReason: finishReason || undefined,
        },
    };
};

// Schema for generating sentence creation exercises from lesson
export const SentenceCreationFromLessonInputSchema = z.object({
    lesson: lessonSchemaZ.describe('The lesson to create exercises from'),
    exerciseCount: z.number().describe('Number of exercises to generate'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
    baseLanguage: z.string().describe('Base language (user native language)'),
    targetLanguage: z.string().describe('Target language (language being learned)'),
});

export const SentenceCreationFromLessonOutputSchema = z.object({
    exercises: z.array(sentenceCreationExerciseSchemaZ.omit({ _id: true })).describe('Array of sentence creation exercises'),
});

// Flow for generating sentence creation exercises from a lesson
export const generateSentenceCreationFromLessonFlow = async (
    input: z.infer<typeof SentenceCreationFromLessonInputSchema>
): Promise<{ output: z.infer<typeof SentenceCreationFromLessonOutputSchema>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    const startTime = performance.now();

    logger.info(`[Exercises SC] Starting sentence creation generation from lesson`);
    logger.info(`[Exercises SC] Using ${modelConfig.displayName}`);
    logger.info(`[Exercises SC] Lesson topic: "${input.lesson.topic}"`);
    logger.info(`[Exercises SC] Exercise count: ${input.exerciseCount}`);

    const prompt = createSentenceCreationFromLessonInstructions(
        input.lesson.topic,
        input.lesson.title.base,
        input.lesson.quickSummary.base,
        input.lesson.fullExplanation.base,
        input.exerciseCount,
        input.studentLevel,
        input.baseLanguage,
        input.targetLanguage
    );

    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: prompt,
        output: { schema: SentenceCreationFromLessonOutputSchema },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Exercises SC] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Exercises SC] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Exercises SC] Output tokens: ${usage?.outputTokens || 0}`);

    if (!output) throw new Error('Failed to generate sentence creation exercises from lesson');

    const totalTime = performance.now() - startTime;
    logger.info(`[Exercises SC] Total time: ${totalTime.toFixed(2)}ms`);
    logger.info(`[Exercises SC] Generated ${output.exercises.length} exercises`);

    return {
        output,
        usage: {
            inputTokens: usage?.inputTokens || 0,
            outputTokens: usage?.outputTokens || 0,
            totalTokens: usage?.totalTokens || 0,
            modelUsed: modelConfig.name,
            executionTimeMs: totalTime,
            finishReason: finishReason || undefined,
        },
    };
};

// Sentence Judging Flow

export const JudgeSentenceInputSchema = z.object({
    prompt: z.string().describe('The exercise prompt in target language'),
    promptBase: z.string().describe('The exercise prompt in base language'),
    referenceAnswer: z.string().describe('Reference answer for the exercise'),
    context: z.string().optional().describe('Additional context or constraints'),
    userAnswer: z.string().describe('The student\'s answer to judge'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
    baseLanguage: z.string().describe('Base language (user native language)'),
    targetLanguage: z.string().describe('Target language (language being learned)'),
});

export const JudgeSentenceOutputSchema = z.object({
    score: z.number().min(0).max(100).describe('Score from 0-100'),
    feedback: z.string().describe('Detailed feedback in base language'),
});

// Flow for judging a student's sentence
export const judgeSentenceFlow = async (
    input: z.infer<typeof JudgeSentenceInputSchema>
): Promise<{ output: z.infer<typeof JudgeSentenceOutputSchema>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    const startTime = performance.now();

    logger.info(`[Judge Sentence] Starting sentence evaluation`);
    logger.info(`[Judge Sentence] Using ${modelConfig.displayName}`);
    logger.info(`[Judge Sentence] Student level: ${input.studentLevel}`);
    logger.info(`[Judge Sentence] User answer: "${input.userAnswer}"`);

    const prompt = judgeSentenceInstructions(
        input.prompt,
        input.promptBase,
        input.referenceAnswer,
        input.context,
        input.userAnswer,
        input.studentLevel,
        input.baseLanguage,
        input.targetLanguage
    );

    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: prompt,
        output: { schema: JudgeSentenceOutputSchema },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Judge Sentence] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Judge Sentence] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Judge Sentence] Output tokens: ${usage?.outputTokens || 0}`);
    logger.info(`[Judge Sentence] Score: ${output?.score || 0}`);

    if (!output) throw new Error('Failed to judge sentence');

    const totalTime = performance.now() - startTime;
    logger.info(`[Judge Sentence] Total time: ${totalTime.toFixed(2)}ms`);

    return {
        output,
        usage: {
            inputTokens: usage?.inputTokens || 0,
            outputTokens: usage?.outputTokens || 0,
            totalTokens: usage?.totalTokens || 0,
            modelUsed: modelConfig.name,
            executionTimeMs: totalTime,
            finishReason: finishReason || undefined,
        },
    };
};