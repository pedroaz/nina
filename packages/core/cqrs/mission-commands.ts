import { connectDatabase } from "../database/database";
import { Mission, MissionModel } from "../entities/mission";
import { createMissionFlow } from "../llm/mission-flows";
import { getUserById } from "./user-queries";
import { savePromptMetadataCommand } from "./prompt-metadata-commands";
import { ValidationError, NotFoundError, DatabaseError, ExternalServiceError } from "../errors";

export interface CreateMissionRequestData {
    userId: string;
    topic: string;
}

export async function createMissionCommand(
    data: CreateMissionRequestData,
): Promise<Mission> {
    if (!data.userId) {
        throw new ValidationError('User ID is required');
    }
    if (!data.topic?.trim()) {
        throw new ValidationError('Topic is required');
    }

    try {
        await connectDatabase();
        const user = await getUserById(data.userId);

        if (!user) {
            throw new NotFoundError(`User not found: ${data.userId}`);
        }

        const { mission: llmResult, usage } = await createMissionFlow({
            topic: data.topic,
            baseLanguage: user.baseLanguage,
            targetLanguage: user.targetLanguage,
            studentLevel: user.level,
        });

        if (!llmResult) {
            throw new ExternalServiceError('Failed to generate mission from LLM');
        }

        const missionObject = new MissionModel({
            title: llmResult.title,
            scenario: llmResult.scenario,
            difficulty: llmResult.difficulty,
            objectives: llmResult.objectives,
            studentData: {
                userId: user._id,
                userName: user.name,
                preferredLanguage: user.baseLanguage,
                studentLevel: user.level,
            },
        });

        await missionObject.save();

        const promptMetadata = await savePromptMetadataCommand({
            missionId: missionObject._id.toString(),
            operation: 'mission_creation',
            modelUsed: usage.modelUsed as 'gpt-5-nano' | 'gpt-4o-mini',
            inputTokens: usage.inputTokens,
            outputTokens: usage.outputTokens,
            totalTokens: usage.totalTokens,
            userId: user._id.toString(),
            executionTimeMs: usage.executionTimeMs,
            finishReason: usage.finishReason,
        });

        missionObject.creationPromptMetadataId = promptMetadata._id.toString();
        await missionObject.save();

        return missionObject;
    } catch (error) {
        if (error instanceof ValidationError || error instanceof NotFoundError || error instanceof ExternalServiceError) {
            throw error;
        }
        throw new DatabaseError('Failed to create mission', error);
    }
}

export interface DeleteMissionRequestData {
    requestId: string;
}

export async function deleteMissionCommand(
    data: DeleteMissionRequestData,
): Promise<void> {
    if (!data.requestId) {
        throw new ValidationError('Mission ID is required');
    }

    try {
        await connectDatabase();
        const result = await MissionModel.deleteOne({
            _id: data.requestId,
        }).exec();

        if (result.deletedCount === 0) {
            throw new NotFoundError(`Mission not found: ${data.requestId}`);
        }
    } catch (error) {
        if (error instanceof ValidationError || error instanceof NotFoundError) {
            throw error;
        }
        throw new DatabaseError(`Failed to delete mission: ${data.requestId}`, error);
    }
}
