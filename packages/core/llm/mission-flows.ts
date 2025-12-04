
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

    console.log(`[Mission Chat] Starting mission chat`);
    console.log(`[Mission Chat] Using ${modelConfig.displayName}`);
    console.log(`[Mission Chat] Mission: "${input.missionTitle}"`);

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

    console.log(`[Mission Chat] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    console.log(`[Mission Chat] Input tokens: ${usage?.inputTokens || 0}`);
    console.log(`[Mission Chat] Output tokens: ${usage?.outputTokens || 0}`);

    const totalTime = performance.now() - startTime;
    console.log(`[Mission Chat] Total time: ${totalTime.toFixed(2)}ms`);

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

    console.log(`[Mission Evaluation] Starting evaluation`);
    console.log(`[Mission Evaluation] Using ${modelConfig.displayName}`);
    console.log(`[Mission Evaluation] Mission: "${input.missionTitle}"`);

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

    console.log(`[Mission Evaluation] Generation time: ${(generateEnd - generateStart).toFixed(2)}ms`);
    console.log(`[Mission Evaluation] Score: ${output?.score || 0}`);

    if (!output) throw new Error('Failed to evaluate mission');

    const totalTime = performance.now() - startTime;
    console.log(`[Mission Evaluation] Total time: ${totalTime.toFixed(2)}ms`);

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
