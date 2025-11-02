import mongoose from 'mongoose';
import { STUDENT_LEVELS, StudentLevel, studentLevelSchemaZ } from './student';
import { z } from 'zod';


export const userSchemaZ = z.object({
    _id: z.string(),
    __v: z.number(),
    name: z.string(),
    email: z.string(),
    level: studentLevelSchemaZ,
});

export const userSchemaM = new mongoose.Schema({
    name: String,
    email: String,
    level: {
        type: String,
        enum: STUDENT_LEVELS,
        required: true
    }
}, {
    timestamps: true
});

export type User = z.infer<typeof userSchemaZ>;

export const UserModel =
    (mongoose.models.users as mongoose.Model<User> | undefined) ??
    mongoose.model<User>('users', userSchemaM);
