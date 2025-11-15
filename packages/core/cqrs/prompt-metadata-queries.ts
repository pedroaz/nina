import { connectDatabase } from '../database/database';
import { PromptMetadata, PromptMetadataModel } from '../entities/prompt-metadata';

export async function getPromptMetadataByLessonId(
    lessonId: string
): Promise<PromptMetadata[]> {
    await connectDatabase();
    return PromptMetadataModel.find({ lessonId })
        .sort({ timestamp: -1 })
        .lean()
        .exec();
}

export async function getPromptMetadataById(
    id: string
): Promise<PromptMetadata | null> {
    await connectDatabase();
    return PromptMetadataModel.findById(id).lean().exec();
}

export async function getPromptMetadataByUserId(
    userId: string
): Promise<PromptMetadata[]> {
    await connectDatabase();
    return PromptMetadataModel.find({ userId })
        .sort({ timestamp: -1 })
        .lean()
        .exec();
}
