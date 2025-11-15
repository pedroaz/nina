import mongoose from 'mongoose';
import { z } from 'zod';

/**
 * Prompt Metadata Entity
 * Tracks LLM usage, tokens, and costs for all AI operations
 */

export const promptOperationTypeZ = z.enum([
    'lesson_creation',
    'extra_section',
    'chat',
    'flashcard_generation',
]);

export type PromptOperationType = z.infer<typeof promptOperationTypeZ>;

export const modelNameZ = z.enum(['gpt-5-nano', 'gpt-4o-mini']);

export type PromptModelName = z.infer<typeof modelNameZ>;

export const promptMetadataSchemaZ = z.object({
    _id: z.string(),
    __v: z.number(),
    lessonId: z.string().optional(),
    operation: promptOperationTypeZ,
    modelUsed: modelNameZ,
    inputTokens: z.number(),
    outputTokens: z.number(),
    totalTokens: z.number(),
    inputCost: z.number(), // USD
    outputCost: z.number(), // USD
    totalCost: z.number(), // USD
    timestamp: z.date(),
    userId: z.string(),
    executionTimeMs: z.number(),
    finishReason: z.string().optional(),
});

export type PromptMetadata = z.infer<typeof promptMetadataSchemaZ>;

export const promptMetadataSchema = new mongoose.Schema<PromptMetadata>({
    lessonId: { type: String, required: false },
    operation: {
        type: String,
        required: true,
        enum: ['lesson_creation', 'extra_section', 'chat', 'flashcard_generation']
    },
    modelUsed: {
        type: String,
        required: true,
        enum: ['gpt-5-nano', 'gpt-4o-mini']
    },
    inputTokens: { type: Number, required: true },
    outputTokens: { type: Number, required: true },
    totalTokens: { type: Number, required: true },
    inputCost: { type: Number, required: true },
    outputCost: { type: Number, required: true },
    totalCost: { type: Number, required: true },
    timestamp: { type: Date, required: true, default: Date.now },
    userId: { type: String, required: true },
    executionTimeMs: { type: Number, required: true },
    finishReason: { type: String, required: false },
});

// Add index for efficient queries
promptMetadataSchema.index({ lessonId: 1 });
promptMetadataSchema.index({ userId: 1 });
promptMetadataSchema.index({ timestamp: -1 });

export const PromptMetadataModel =
    (mongoose.models.promptmetadata as mongoose.Model<PromptMetadata> | undefined) ??
    mongoose.model<PromptMetadata>('promptmetadata', promptMetadataSchema);
