import { z } from 'zod';
import { Schema } from 'mongoose';

export const dualLanguageSchemaZ = z.object({
    base: z.string(),
    german: z.string(),
});

export const dualLanguageSchemaM = new Schema({
    base: { type: String, required: true },
    german: { type: String, required: true }
}, {
    _id: false,
    id: false,
    versionKey: false,
});