import { NextRequest, NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/get-authenticated-user";
import { getMissionById, getUserById, logger, globalSessionStore } from "@core/index";
import { z } from "zod";

const MissionCheckRequestSchema = z.object({
    sessionId: z.string().min(1, "Session ID is required"),
});

interface MissionChatSession {
    missionId: string;
    userId: string;
    messages: Array<{ role: 'user' | 'assistant'; content: string }>;
}

const EvaluationOutputSchema = z.object({
    score: z.number().min(0).max(100),
    feedback: z.string(),
    grammarScore: z.number().min(0).max(100).optional(),
    objectiveProgress: z.array(z.object({
        objective: z.string(),
        completed: z.boolean(),
    })).optional(),
});

export async function POST(
    request: NextRequest,
    context: { params: Promise<{ id: string }> }
) {
    try {
        const user = await getAuthenticatedUser();
        const userDetails = await getUserById(user._id);

        if (!userDetails) {
            return NextResponse.json(
                { error: "User details not found" },
                { status: 404 }
            );
        }

        const { id: missionId } = await context.params;
        const body = await request.json();

        const validation = MissionCheckRequestSchema.safeParse(body);
        if (!validation.success) {
            return NextResponse.json(
                { error: "Invalid request", details: validation.error.errors },
                { status: 400 }
            );
        }

        const { sessionId } = validation.data;

        // Fetch mission
        const mission = await getMissionById(missionId);
        if (!mission) {
            return NextResponse.json(
                { error: "Mission not found" },
                { status: 404 }
            );
        }

        // Load session
        logger.info(`[Mission Check API] Looking for session: ${sessionId}`);
        const sessionData = await globalSessionStore.get(sessionId);
        if (!sessionData) {
            logger.error(`[Mission Check API] Session not found: ${sessionId}`);
            return NextResponse.json(
                { error: "Session not found or expired" },
                { status: 404 }
            );
        }

        const session = sessionData.state as MissionChatSession;

        // Verify session belongs to this user and mission
        const currentUserId = user._id.toString ? user._id.toString() : String(user._id);
        const sessionUserId = session.userId.toString ? session.userId.toString() : String(session.userId);
        const currentMissionId = missionId.toString ? missionId.toString() : String(missionId);
        const sessionMissionId = session.missionId.toString ? session.missionId.toString() : String(session.missionId);

        logger.info(`[Mission Check API] Verifying authorization - userId: "${currentUserId}" vs "${sessionUserId}", missionId: "${currentMissionId}" vs "${sessionMissionId}"`);
        if (sessionUserId !== currentUserId || sessionMissionId !== currentMissionId) {
            logger.error(`[Mission Check API] Authorization failed - userId match: ${sessionUserId === currentUserId}, missionId match: ${sessionMissionId === currentMissionId}`);
            return NextResponse.json(
                { error: "Unauthorized" },
                { status: 403 }
            );
        }

        // Build conversation summary for evaluation
        const conversationSummary = session.messages
            .map(msg => `${msg.role === 'user' ? 'Student' : 'Assistant'}: ${msg.content}`)
            .join('\n');

        // Create evaluation prompt
        const evaluationPrompt = `You are an expert language teacher evaluating a language learning mission.

Mission: ${mission.title}
Objectives (${mission.objectives.length} total): ${mission.objectives.join(', ')}
Student Level: ${mission.studentData.studentLevel}
Target Language: ${userDetails.targetLanguage}

Conversation:
${conversationSummary}

EVALUATION INSTRUCTIONS:
1. Check EACH objective carefully. Mark as completed ONLY if the student clearly demonstrated or said that objective.
2. Score grammar on a scale of 0-100 based on:
   - Accuracy: Are there grammatical errors?
   - Complexity: Are sentences appropriate for the level?
   - Consistency: Is the language used correctly throughout?
3. Calculate overall score based on:
   - Objective completion: 60% of score (number of completed objectives / total objectives * 60)
   - Grammar accuracy: 30% of score
   - Engagement: 10% of score (effort, participation, vocabulary)

IMPORTANT SCORING RULES:
- If only 1 of 5 objectives are completed, the maximum score should be around 20-30, NOT 70
- Score should heavily reflect objective completion
- Provide honest, constructive feedback

Return JSON with:
- score: number (0-100) - MUST reflect objective completion heavily
- grammarScore: number (0-100) - detailed grammar assessment
- feedback: string (detailed feedback in ${userDetails.baseLanguage}, be encouraging but honest about what needs improvement)
- objectiveProgress: array of {objective: string, completed: boolean}`;

        logger.info(`[Mission Check API] Evaluating mission ${missionId} session ${sessionId}`);

        // Dynamically import chatAi to avoid server-side bundle issues
        const { chatAi } = await import('@core/index');

        // Generate evaluation using Genkit
        const response = await chatAi.generate({
            prompt: evaluationPrompt,
            output: { schema: EvaluationOutputSchema },
        });

        if (!response.output) {
            throw new Error('Failed to generate evaluation');
        }

        const evaluation = response.output;

        logger.info(`[Mission Check API] Evaluation complete. Score: ${evaluation.score}, Grammar: ${evaluation.grammarScore}`);

        return NextResponse.json(
            {
                score: evaluation.score,
                feedback: evaluation.feedback,
                grammarScore: evaluation.grammarScore,
                objectiveProgress: evaluation.objectiveProgress,
                usage: {
                    inputTokens: response.usage?.inputTokens || 0,
                    outputTokens: response.usage?.outputTokens || 0,
                    totalTokens: response.usage?.totalTokens || 0,
                },
            },
            { status: 200 }
        );
    } catch (error: any) {
        logger.error(`[Mission Check API] Error: ${error.message}`);
        console.error("Error in mission check:", error);
        return NextResponse.json(
            { error: error.message || "Failed to evaluate mission" },
            { status: 500 }
        );
    }
}
