import { z } from 'zod';
import { Schema } from 'mongoose';

export const dualLanguageSchemaZ = z.object({
    base: z.string(),
    target: z.string(),
});

export const dualLanguageSchemaM = new Schema({
    base: { type: String, required: true },
    target: { type: String, required: true }
}, {
    _id: false,
    id: false,
    versionKey: false,
});