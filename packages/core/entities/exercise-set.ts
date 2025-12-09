import mongoose from 'mongoose';
import { studentDataSchemaZ, studentSchemaM } from './student';
import { dualLanguageSchemaZ, dualLanguageSchemaM } from './base';
import { z } from 'zod';

// Multiple Choice Exercise schema
export const multipleChoiceExerciseSchemaZ = z.object({
    _id: z.string(),
    question: dualLanguageSchemaZ,
    options: z.array(dualLanguageSchemaZ).length(4),
    correctOptionIndex: z.number().min(0).max(3),
});

export type MultipleChoiceExercise = z.infer<typeof multipleChoiceExerciseSchemaZ>;

export const multipleChoiceExerciseSchemaM = new mongoose.Schema({
    question: { type: dualLanguageSchemaM, required: true },
    options: { type: [dualLanguageSchemaM], required: true },
    correctOptionIndex: { type: Number, required: true, min: 0, max: 3 },
}, {
    timestamps: false,
});

// Sentence Creation Exercise schema
export const sentenceCreationExerciseSchemaZ = z.object({
    _id: z.string(),
    prompt: dualLanguageSchemaZ,
    referenceAnswer: z.string(), // In target language
    context: z.string().optional(), // Additional context for the exercise
});

export type SentenceCreationExercise = z.infer<typeof sentenceCreationExerciseSchemaZ>;

export const sentenceCreationExerciseSchemaM = new mongoose.Schema({
    prompt: { type: dualLanguageSchemaM, required: true },
    referenceAnswer: { type: String, required: true },
    context: { type: String, required: false },
}, {
    timestamps: false,
});

// Exercise Set Type
export const exerciseSetTypeSchemaZ = z.enum(['multiple_choice', 'sentence_creation']);
export type ExerciseSetType = z.infer<typeof exerciseSetTypeSchemaZ>;

// Base Exercise Set schema (common fields)
const baseExerciseSetSchemaZ = z.object({
    _id: z.string(),
    __v: z.number(),
    title: z.string(),
    topic: z.string(),
    studentData: studentDataSchemaZ,
    type: exerciseSetTypeSchemaZ,
    sourceLesson: z.string().optional(), // Optional reference to lesson ID
    createdAt: z.date(),
    updatedAt: z.date(),
});

// Multiple Choice Exercise Set
export const multipleChoiceExerciseSetSchemaZ = baseExerciseSetSchemaZ.extend({
    type: z.literal('multiple_choice'),
    exercises: z.array(multipleChoiceExerciseSchemaZ),
});

export type MultipleChoiceExerciseSet = z.infer<typeof multipleChoiceExerciseSetSchemaZ>;

// Sentence Creation Exercise Set
export const sentenceCreationExerciseSetSchemaZ = baseExerciseSetSchemaZ.extend({
    type: z.literal('sentence_creation'),
    exercises: z.array(sentenceCreationExerciseSchemaZ),
});

export type SentenceCreationExerciseSet = z.infer<typeof sentenceCreationExerciseSetSchemaZ>;

// Union type for all exercise sets
export const exerciseSetSchemaZ = z.discriminatedUnion('type', [
    multipleChoiceExerciseSetSchemaZ,
    sentenceCreationExerciseSetSchemaZ,
]);

export type ExerciseSet = z.infer<typeof exerciseSetSchemaZ>;

// Mongoose schema (uses type discriminator)
// Create a generic subdocument schema that accepts both exercise types
const exerciseSubdocSchema = new mongoose.Schema({}, {
    strict: false, // Allow any fields (MC or SC)
    _id: true, // Auto-generate _id for each exercise
    timestamps: false
});

export const exerciseSetSchema = new mongoose.Schema<ExerciseSet>({
    title: { type: String, required: true },
    topic: { type: String, required: true },
    studentData: studentSchemaM,
    type: { type: String, enum: ['multiple_choice', 'sentence_creation'], required: true },
    exercises: [exerciseSubdocSchema],
    sourceLesson: { type: String, required: false },
}, {
    timestamps: true,
    discriminatorKey: 'type',
});

export const ExerciseSetModel =
    (mongoose.models.exerciseSets as mongoose.Model<ExerciseSet> | undefined) ??
    mongoose.model<ExerciseSet>('exerciseSets', exerciseSetSchema);
