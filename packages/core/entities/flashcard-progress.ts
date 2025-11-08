import mongoose from 'mongoose';
import { z } from 'zod';

// Card Progress schema (embedded in progress document)
export const cardProgressSchemaZ = z.object({
    cardId: z.string(),
    knowCount: z.number(),
    dontKnowCount: z.number(),
    lastAnswer: z.enum(['know', 'dontKnow']).optional(),
});

export type CardProgress = z.infer<typeof cardProgressSchemaZ>;

export const cardProgressSchemaM = new mongoose.Schema({
    cardId: { type: String, required: true },
    knowCount: { type: Number, required: true, default: 0 },
    dontKnowCount: { type: Number, required: true, default: 0 },
    lastAnswer: {
        type: String,
        enum: ['know', 'dontKnow'],
        required: false
    },
}, {
    _id: false,
    timestamps: false,
});

// Flash Card Progress schema
export const flashCardProgressSchemaZ = z.object({
    _id: z.string(),
    __v: z.number(),
    deckId: z.string(),
    userId: z.string(),
    cardProgress: z.array(cardProgressSchemaZ),
    updatedAt: z.date(),
    createdAt: z.date(),
});

export type FlashCardProgress = z.infer<typeof flashCardProgressSchemaZ>;

export const flashCardProgressSchema = new mongoose.Schema<FlashCardProgress>({
    deckId: { type: String, required: true },
    userId: { type: String, required: true },
    cardProgress: [cardProgressSchemaM],
}, {
    timestamps: true,
});

// Create compound index for efficient lookups
flashCardProgressSchema.index({ deckId: 1, userId: 1 }, { unique: true });

export const FlashCardProgressModel =
    (mongoose.models.flashCardProgress as mongoose.Model<FlashCardProgress> | undefined) ??
    mongoose.model<FlashCardProgress>('flashCardProgress', flashCardProgressSchema);
