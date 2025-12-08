
// Mission Creation Flow

import { chatAi, ai, getModelConfig, logger, MODEL_CATEGORIES, studentLevelSchemaZ, UsageMetadata } from "../";
import { z } from "zod";

export const MissionCreationInputSchema = z.object({
    topic: z.string().describe('User topic for the mission'),
    baseLanguage: z.string().describe('Base language'),
    targetLanguage: z.string().describe('Target language'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
});

export const MissionCreationOutputSchema = z.object({
    title: z.string().describe('Title of the mission'),
    scenario: z.string().describe('Scenario description'),
    difficulty: z.enum(['A1', 'A2', 'B1', 'B2', 'C1', 'C2']).describe('Difficulty level'),
    objectives: z.array(z.string()).describe('List of 3-5 objectives for the mission'),
});

export const createMissionFlow = async (
    input: z.infer<typeof MissionCreationInputSchema>
): Promise<{ mission: z.infer<typeof MissionCreationOutputSchema>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.DETAILED);
    const startTime = performance.now();

    logger.info(`[Mission Creation] Starting mission generation`);
    logger.info(`[Mission Creation] Using ${modelConfig.displayName}`);
    logger.info(`[Mission Creation] Topic: "${input.topic}"`);

    const prompt = `You are an expert language tutor creating a roleplay mission for a student.

Topic: ${input.topic}
Student Level: ${input.studentLevel}
Target Language: ${input.targetLanguage}
Base Language: ${input.baseLanguage}

Create a realistic and engaging roleplay scenario based on the topic.
The scenario should be appropriate for the student's level.
Define 3-5 clear objectives for the student to achieve during the roleplay.
The title should be concise and engaging.
The difficulty should match the student level (A1-C2).

Return a JSON object with the following fields:
- title: The title of the mission
- scenario: A description of the situation and the student's role
- difficulty: The CEFR level (A1, A2, B1, B2, C1, C2)
- objectives: An array of strings, each describing a specific goal`;

    const generateStart = performance.now();
    const response = await ai.generate({
        prompt: prompt,
        output: { schema: MissionCreationOutputSchema },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Mission Creation] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Mission Creation] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Mission Creation] Output tokens: ${usage?.outputTokens || 0}`);

    if (!output) throw new Error('Failed to generate mission');

    const totalTime = performance.now() - startTime;

    return {
        mission: output,
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

// Mission Chat Flow


export const MissionChatInputSchema = z.object({
    missionTitle: z.string().describe('Title of the mission'),
    scenario: z.string().describe('Scenario description'),
    objectives: z.array(z.string()).describe('Mission objectives'),
    userMessage: z.string().describe('User message'),
    chatHistory: z.array(z.object({
        role: z.enum(['user', 'assistant']),
        content: z.string(),
    })).describe('Previous chat messages'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
    targetLanguage: z.string().describe('Target language'),
    baseLanguage: z.string().describe('Base language'),
});

export const MissionChatOutputSchema = z.object({
    response: z.string().describe('Assistant response in target language'),
});

// Flow for mission chat interaction
export const missionChatFlow = async (
    input: z.infer<typeof MissionChatInputSchema>
): Promise<{ output: z.infer<typeof MissionChatOutputSchema>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    const startTime = performance.now();

    logger.info(`[Mission Chat] Starting mission chat`);
    logger.info(`[Mission Chat] Using ${modelConfig.displayName}`);
    logger.info(`[Mission Chat] Mission: "${input.missionTitle}"`);

    const systemPrompt = `You are a ${input.targetLanguage} language tutor conducting a roleplay scenario.

Mission: ${input.missionTitle}
Scenario: ${input.scenario}
Objectives: ${input.objectives.join(', ')}
Student Level: ${input.studentLevel}

Your role:
1. Respond ONLY in ${input.targetLanguage} (never use ${input.baseLanguage} unless the student is completely stuck)
2. Stay in character for the scenario
3. Guide the student to complete the objectives naturally through conversation
4. Use vocabulary and grammar appropriate for ${input.studentLevel} level
5. Be encouraging and patient
6. If the student makes mistakes, gently correct them in context
7. Keep responses concise (2-3 sentences max)`;

    let conversationContext = '';
    if (input.chatHistory.length > 0) {
        conversationContext = '\n\nConversation so far:\n';
        for (const msg of input.chatHistory) {
            const speaker = msg.role === 'user' ? 'Student' : 'You';
            conversationContext += `${speaker}: ${msg.content}\n`;
        }
    }

    const fullPrompt = `${systemPrompt}${conversationContext}\n\nStudent: ${input.userMessage}\n\nYou:`;

    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: fullPrompt,
    });
    const { text, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Mission Chat] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Mission Chat] Input tokens: ${usage?.inputTokens || 0}`);
    logger.info(`[Mission Chat] Output tokens: ${usage?.outputTokens || 0}`);

    const totalTime = performance.now() - startTime;
    logger.info(`[Mission Chat] Total time: ${totalTime.toFixed(2)}ms`);

    return {
        output: { response: text },
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

// Mission Evaluation Flow

export const MissionEvaluationInputSchema = z.object({
    missionTitle: z.string().describe('Title of the mission'),
    objectives: z.array(z.string()).describe('Mission objectives'),
    chatHistory: z.array(z.object({
        role: z.enum(['user', 'assistant']),
        content: z.string(),
    })).describe('Complete chat history'),
    studentLevel: studentLevelSchemaZ.describe('Student proficiency level'),
    targetLanguage: z.string().describe('Target language'),
    baseLanguage: z.string().describe('Base language'),
});

export const MissionEvaluationOutputSchema = z.object({
    score: z.number().min(0).max(100).describe('Score from 0-100'),
    feedback: z.string().describe('Detailed feedback in base language'),
});

// Flow for evaluating mission completion
export const evaluateMissionFlow = async (
    input: z.infer<typeof MissionEvaluationInputSchema>
): Promise<{ output: z.infer<typeof MissionEvaluationOutputSchema>; usage: UsageMetadata }> => {
    const modelConfig = getModelConfig(MODEL_CATEGORIES.FAST);
    const startTime = performance.now();

    logger.info(`[Mission Evaluation] Starting evaluation`);
    logger.info(`[Mission Evaluation] Using ${modelConfig.displayName}`);
    logger.info(`[Mission Evaluation] Mission: "${input.missionTitle}"`);

    const conversationSummary = input.chatHistory.map(msg =>
        `${msg.role === 'user' ? 'Student' : 'Assistant'}: ${msg.content}`
    ).join('\n');

    const prompt = `You are evaluating a language learning mission completion.

Mission: ${input.missionTitle}
Objectives: ${input.objectives.join(', ')}
Student Level: ${input.studentLevel}
Target Language: ${input.targetLanguage}

Conversation:
${conversationSummary}

Evaluate the student's performance based on:
1. Did they complete the mission objectives?
2. Grammar accuracy for their level
3. Vocabulary usage
4. Natural conversation flow
5. Effort and engagement

Provide a score from 0-100 and detailed feedback in ${input.baseLanguage}.
Be encouraging and constructive. Highlight what they did well and areas for improvement.

Return JSON with "score" (number) and "feedback" (string).`;

    const generateStart = performance.now();
    const response = await chatAi.generate({
        prompt: prompt,
        output: { schema: MissionEvaluationOutputSchema },
    });
    const { output, usage, finishReason } = response;
    const generateEnd = performance.now();

    logger.info(`[Mission Evaluation] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    logger.info(`[Mission Evaluation] Score: ${output?.score || 0}`);

    if (!output) throw new Error('Failed to evaluate mission');

    const totalTime = performance.now() - startTime;
    logger.info(`[Mission Evaluation] Total time: ${totalTime.toFixed(2)}ms`);

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
