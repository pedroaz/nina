import { z } from 'zod';
import mongoose from 'mongoose';

export const STUDENT_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"] as const;

export const studentLevelSchemaZ = z.enum(STUDENT_LEVELS);

export const supportedLanguagesSchemaZ = z.enum([
    "english",
    "german",
    "spanish",
    "french",
    "italian",
    "portuguese",
]);

export const studentDataSchemaZ = z.object({
    userId: z.string(),
    userName: z.string(),
    preferredLanguage: supportedLanguagesSchemaZ,
    studentLevel: studentLevelSchemaZ,
});

export type StudentLevel = z.infer<typeof studentLevelSchemaZ>;
export type SupportedLanguages = z.infer<typeof supportedLanguagesSchemaZ>;
export type StudentData = z.infer<typeof studentDataSchemaZ>;

export const studentSchemaM = new mongoose.Schema({
    userId: {
        type: String,
        required: true,
        unique: false
    },
    userName: {
        type: String,
        required: true
    },
    preferredLanguage: {
        type: String,
        enum: ["english", "german", "spanish", "french", "italian", "portuguese"],
        required: true
    },
    studentLevel: {
        type: String,
        enum: ["A1", "A2", "B1", "B2", "C1", "C2"],
        required: true
    }
}, {
    timestamps: true
});