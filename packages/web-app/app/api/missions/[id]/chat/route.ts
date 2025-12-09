import { NextRequest, NextResponse } from "next/server";
import { getAuthenticatedUser } from "@/lib/get-authenticated-user";
import { getMissionById, getUserById, logger, globalSessionStore } from "@core/index";
import { z } from "zod";

const MissionChatRequestSchema = z.object({
    message: z.string().min(1, "Message is required"),
    sessionId: z.string().optional(),
});

interface MissionChatSession {
    missionId: string;
    userId: string;
    messages: Array<{ role: 'user' | 'assistant'; content: string }>;
}

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

        const validation = MissionChatRequestSchema.safeParse(body);
        if (!validation.success) {
            return NextResponse.json(
                { error: "Invalid request", details: validation.error.errors },
                { status: 400 }
            );
        }

        const { message, sessionId } = validation.data;

        // Fetch the mission to get context
        const mission = await getMissionById(missionId);
        if (!mission) {
            return NextResponse.json(
                { error: "Mission not found" },
                { status: 404 }
            );
        }

        // Load or create session
        let session;
        let newSessionId = sessionId || `mission-${missionId}-${user._id}-${Date.now()}`;

        if (sessionId) {
            const sessionData = await globalSessionStore.get(sessionId);
            if (!sessionData) {
                return NextResponse.json(
                    { error: "Session not found or expired" },
                    { status: 404 }
                );
            }
            session = sessionData.state as MissionChatSession;
        } else {
            // Create new session
            session = {
                missionId: missionId,
                userId: user._id.toString ? user._id.toString() : String(user._id),
                messages: [],
            };
        }

        // Add user message to history
        session.messages.push({ role: 'user', content: message });

        // Build system prompt
        const systemPrompt = `You are a ${userDetails.targetLanguage} language tutor conducting a roleplay scenario.

Mission: ${mission.title}
Scenario: ${mission.scenario}
Objectives: ${mission.objectives.join(', ')}
Student Level: ${mission.studentData.studentLevel}

Your role:
1. Respond ONLY in ${userDetails.targetLanguage} (never use ${userDetails.baseLanguage} unless the student is completely stuck)
2. Stay in character for the scenario
3. Guide the student to complete the objectives naturally through conversation
4. Use vocabulary and grammar appropriate for ${mission.studentData.studentLevel} level
5. Be encouraging and patient
6. If the student makes mistakes, gently correct them in context
7. Keep responses concise (2-3 sentences max)`;

        // Build conversation context
        let conversationContext = '';
        if (session.messages.length > 1) {
            conversationContext = '\n\nConversation so far:\n';
            for (const msg of session.messages.slice(0, -1)) {
                const speaker = msg.role === 'user' ? 'Student' : 'Assistant';
                conversationContext += `${speaker}: ${msg.content}\n`;
            }
        }

        const fullPrompt = `${systemPrompt}${conversationContext}\n\nStudent: ${message}\n\nAssistant:`;

        logger.info(`[Mission Chat API] Generating response for mission ${missionId}`);

        // Dynamically import chatAi to avoid server-side bundle issues
        const { chatAi } = await import('@core/index');

        // Generate response using Genkit
        const response = await chatAi.generate({
            prompt: fullPrompt,
        });

        const assistantMessage = response.text;

        // Add assistant response to history
        session.messages.push({ role: 'assistant', content: assistantMessage });

        // Save updated session
        logger.info(`[Mission Chat API] Saving session: ${newSessionId}`);
        await globalSessionStore.save(newSessionId, {
            state: session,
        } as any);

        logger.info(`[Mission Chat API] Response generated. Session: ${newSessionId}`);

        return NextResponse.json(
            {
                sessionId: newSessionId,
                message: assistantMessage,
                usage: {
                    inputTokens: response.usage?.inputTokens || 0,
                    outputTokens: response.usage?.outputTokens || 0,
                    totalTokens: response.usage?.totalTokens || 0,
                },
            },
            { status: 200 }
        );
    } catch (error: any) {
        logger.error(`[Mission Chat API] Error: ${error.message}`);
        console.error("Error in mission chat:", error);
        return NextResponse.json(
            { error: error.message || "Failed to process message" },
            { status: 500 }
        );
    }
}
