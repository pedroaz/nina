import { chatAi, logger } from "@core/index";
import { z } from "zod";

const EvaluationOutputSchema = z.object({
    score: z.number().min(0).max(100),
    feedback: z.string(),
    objectiveProgress: z.array(z.object({
        objective: z.string(),
        completed: z.boolean(),
    })).optional(),
});

interface MissionContext {
    title: string;
    scenario: string;
    objectives: string[];
    studentLevel: string;
    targetLanguage: string;
    baseLanguage: string;
}

interface ChatMessage {
    role: 'user' | 'assistant';
    content: string;
}

export async function generateMissionResponse(
    userMessage: string,
    messages: ChatMessage[],
    context: MissionContext
): Promise<string> {
    const systemPrompt = `You are a ${context.targetLanguage} language tutor conducting a roleplay scenario.

Mission: ${context.title}
Scenario: ${context.scenario}
Objectives: ${context.objectives.join(', ')}
Student Level: ${context.studentLevel}

Your role:
1. Respond ONLY in ${context.targetLanguage} (never use ${context.baseLanguage} unless the student is completely stuck)
2. Stay in character for the scenario
3. Guide the student to complete the objectives naturally through conversation
4. Use vocabulary and grammar appropriate for ${context.studentLevel} level
5. Be encouraging and patient
6. If the student makes mistakes, gently correct them in context
7. Keep responses concise (2-3 sentences max)`;

    // Build conversation context
    let conversationContext = '';
    if (messages.length > 0) {
        conversationContext = '\n\nConversation so far:\n';
        for (const msg of messages) {
            const speaker = msg.role === 'user' ? 'Student' : 'Assistant';
            conversationContext += `${speaker}: ${msg.content}\n`;
        }
    }

    const fullPrompt = `${systemPrompt}${conversationContext}\n\nStudent: ${userMessage}\n\nAssistant:`;

    logger.info(`[Mission Chat Service] Generating response`);

    try {
        const response = await chatAi.generate({
            prompt: fullPrompt,
        });

        return response.text;
    } catch (error) {
        logger.error(`[Mission Chat Service] Error generating response: ${error}`);
        throw error;
    }
}

export async function evaluateMissionConversation(
    messages: ChatMessage[],
    context: MissionContext
): Promise<z.infer<typeof EvaluationOutputSchema>> {
    const conversationSummary = messages
        .map(msg => `${msg.role === 'user' ? 'Student' : 'Assistant'}: ${msg.content}`)
        .join('\n');

    const evaluationPrompt = `You are evaluating a language learning mission completion.

Mission: ${context.title}
Objectives: ${context.objectives.join(', ')}
Student Level: ${context.studentLevel}
Target Language: ${context.targetLanguage}

Conversation:
${conversationSummary}

Evaluate the student's performance based on:
1. Did they complete the mission objectives? (List which ones were completed)
2. Grammar accuracy for their level
3. Vocabulary usage
4. Natural conversation flow
5. Effort and engagement

Provide:
- A score from 0-100
- Detailed feedback in ${context.baseLanguage} (be encouraging and constructive)
- Which objectives were completed (true/false for each)

Return JSON with:
- score: number (0-100)
- feedback: string (detailed feedback in base language)
- objectiveProgress: array of {objective: string, completed: boolean}`;

    logger.info(`[Mission Chat Service] Evaluating mission completion`);

    try {
        const response = await chatAi.generate({
            prompt: evaluationPrompt,
            output: { schema: EvaluationOutputSchema },
        });

        if (!response.output) {
            throw new Error('Failed to generate evaluation');
        }

        return response.output;
    } catch (error) {
        logger.error(`[Mission Chat Service] Error evaluating mission: ${error}`);
        throw error;
    }
}
