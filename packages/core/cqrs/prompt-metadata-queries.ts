import { connectDatabase } from '../database/database';
import { PromptMetadata, PromptMetadataModel } from '../entities/prompt-metadata';
import { DatabaseError, ValidationError } from '../errors';

export async function getPromptMetadataByLessonId(
    lessonId: string
): Promise<PromptMetadata[]> {
    if (!lessonId) {
        throw new ValidationError('Lesson ID is required');
    }

    try {
        await connectDatabase();
        return await PromptMetadataModel.find({ lessonId })
            .sort({ timestamp: -1 })
            .lean()
            .exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch prompt metadata for lesson: ${lessonId}`, error);
    }
}

export async function getPromptMetadataById(
    id: string
): Promise<PromptMetadata | null> {
    if (!id) {
        throw new ValidationError('Metadata ID is required');
    }

    try {
        await connectDatabase();
        return await PromptMetadataModel.findById(id).lean().exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch prompt metadata: ${id}`, error);
    }
}

export async function getPromptMetadataByUserId(
    userId: string
): Promise<PromptMetadata[]> {
    if (!userId) {
        throw new ValidationError('User ID is required');
    }

    try {
        await connectDatabase();
        return await PromptMetadataModel.find({ userId })
            .sort({ timestamp: -1 })
            .lean()
            .exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch prompt metadata for user: ${userId}`, error);
    }
}
