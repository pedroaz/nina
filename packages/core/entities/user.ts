import mongoose from 'mongoose';
import { STUDENT_LEVELS, StudentLevel, studentLevelSchemaZ, supportedLanguagesSchemaZ, SupportedLanguages } from './student';
import { z } from 'zod';

// Flash card display preference
export const flashCardDisplayPreferenceSchemaZ = z.enum(['base-first', 'target-first']);

export type FlashCardDisplayPreference = z.infer<typeof flashCardDisplayPreferenceSchemaZ>;

export const userSchemaZ = z.object({
    _id: z.string(),
    __v: z.number(),
    name: z.string(),
    email: z.string(),
    level: studentLevelSchemaZ,
    flashCardDisplayPreference: flashCardDisplayPreferenceSchemaZ.optional(),
    baseLanguage: supportedLanguagesSchemaZ,
    targetLanguage: supportedLanguagesSchemaZ,
});

export const userSchemaM = new mongoose.Schema({
    name: String,
    email: String,
    level: {
        type: String,
        enum: STUDENT_LEVELS,
        required: true
    },
    flashCardDisplayPreference: {
        type: String,
        enum: ['base-first', 'target-first'],
        required: false,
        default: 'base-first',
    },
    baseLanguage: {
        type: String,
        enum: ["english", "german", "spanish", "french", "italian", "portuguese"],
        required: true,
        default: 'english',
    },
    targetLanguage: {
        type: String,
        enum: ["english", "german", "spanish", "french", "italian", "portuguese"],
        required: true,
        default: 'german',
    }
}, {
    timestamps: true
});

export type User = z.infer<typeof userSchemaZ>;

export const UserModel =
    (mongoose.models.users as mongoose.Model<User> | undefined) ??
    mongoose.model<User>('users', userSchemaM);
