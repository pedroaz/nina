import { connectDatabase } from '../database/database';
import { PromptMetadata, PromptMetadataModel, PromptOperationType, PromptModelName } from '../entities/prompt-metadata';
import { calculateCost, ModelName } from '../llm/model-config';
import { logger } from "@core/index";

export interface SavePromptMetadataRequestData {
    lessonId?: string;
    operation: PromptOperationType;
    modelUsed: PromptModelName;
    inputTokens: number;
    outputTokens: number;
    totalTokens: number;
    userId: string;
    executionTimeMs: number;
    finishReason?: string;
}

export async function savePromptMetadataCommand(
    data: SavePromptMetadataRequestData
): Promise<PromptMetadata> {
    await connectDatabase();

    // Calculate costs based on model and token usage
    const costBreakdown = calculateCost(
        data.modelUsed as ModelName,
        data.inputTokens,
        data.outputTokens
    );

    const promptMetadata = new PromptMetadataModel({
        lessonId: data.lessonId,
        operation: data.operation,
        modelUsed: data.modelUsed,
        inputTokens: data.inputTokens,
        outputTokens: data.outputTokens,
        totalTokens: data.totalTokens,
        inputCost: costBreakdown.inputCost,
        outputCost: costBreakdown.outputCost,
        totalCost: costBreakdown.totalCost,
        timestamp: new Date(),
        userId: data.userId,
        executionTimeMs: data.executionTimeMs,
        finishReason: data.finishReason,
    });

    await promptMetadata.save();

    logger.info(`[Prompt Metadata] Saved metadata for ${data.operation}`);
    logger.info(`[Prompt Metadata] Cost: $${costBreakdown.totalCost.toFixed(6)}`);

    return promptMetadata;
}
