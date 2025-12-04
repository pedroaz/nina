import mongoose from 'mongoose';
import { z } from 'zod';

export const chatMessageSchemaZ = z.object({
    role: z.enum(['user', 'assistant']),
    content: z.string(),
    timestamp: z.date(),
});

export type ChatMessage = z.infer<typeof chatMessageSchemaZ>;

export const missionChatSchemaZ = z.object({
    _id: z.string(),
    __v: z.number(),
    missionId: z.string(),
    userId: z.string(),
    messages: z.array(chatMessageSchemaZ),
    score: z.number().optional(),
    feedback: z.string().optional(),
    completed: z.boolean(),
    createdAt: z.date(),
    completedAt: z.date().optional(),
});

export type MissionChat = z.infer<typeof missionChatSchemaZ>;

const chatMessageSchema = new mongoose.Schema({
    role: { type: String, required: true, enum: ['user', 'assistant'] },
    content: { type: String, required: true },
    timestamp: { type: Date, required: true, default: Date.now },
}, { _id: false });

export const missionChatSchema = new mongoose.Schema<MissionChat>({
    missionId: { type: String, required: true },
    userId: { type: String, required: true },
    messages: [chatMessageSchema],
    score: { type: Number, required: false },
    feedback: { type: String, required: false },
    completed: { type: Boolean, required: true, default: false },
    createdAt: { type: Date, required: true, default: Date.now },
    completedAt: { type: Date, required: false },
});

// Add indexes
missionChatSchema.index({ missionId: 1 });
missionChatSchema.index({ userId: 1 });

export const MissionChatModel =
    (mongoose.models.missionchats as mongoose.Model<MissionChat> | undefined) ??
    mongoose.model<MissionChat>('missionchats', missionChatSchema);
