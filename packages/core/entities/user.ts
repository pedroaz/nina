import mongoose from 'mongoose';
import { STUDENT_LEVELS, StudentLevel, studentLevelSchemaZ } from './student';
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
    }
}, {
    timestamps: true
});

export type User = z.infer<typeof userSchemaZ>;

export const UserModel =
    (mongoose.models.users as mongoose.Model<User> | undefined) ??
    mongoose.model<User>('users', userSchemaM);
