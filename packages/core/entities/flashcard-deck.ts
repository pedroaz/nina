import mongoose from 'mongoose';
import { studentDataSchemaZ, studentSchemaM } from './student';
import { z } from 'zod';

// Flash Card schema (embedded in deck)
export const flashCardSchemaZ = z.object({
    _id: z.string(),
    base: z.string(),    // English text (full sentence)
    german: z.string(),  // German translation (full sentence)
});

export type FlashCard = z.infer<typeof flashCardSchemaZ>;

export const flashCardSchemaM = new mongoose.Schema({
    base: { type: String, required: true },
    german: { type: String, required: true },
}, {
    timestamps: false,
});

// Flash Card Deck schema
export const flashCardDeckSchemaZ = z.object({
    _id: z.string(),
    __v: z.number(),
    title: z.string(),
    studentData: studentDataSchemaZ,
    cards: z.array(flashCardSchemaZ),
    sourceLesson: z.string().optional(), // Optional reference to lesson ID
    createdAt: z.date(),
    updatedAt: z.date(),
});

export type FlashCardDeck = z.infer<typeof flashCardDeckSchemaZ>;

export const flashCardDeckSchema = new mongoose.Schema<FlashCardDeck>({
    title: { type: String, required: true },
    studentData: studentSchemaM,
    cards: [flashCardSchemaM],
    sourceLesson: { type: String, required: false },
}, {
    timestamps: true,
});

export const FlashCardDeckModel =
    (mongoose.models.flashCardDecks as mongoose.Model<FlashCardDeck> | undefined) ??
    mongoose.model<FlashCardDeck>('flashCardDecks', flashCardDeckSchema);
