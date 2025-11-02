import { z } from 'zod';

export const exerciseTypeSchemaZ = z.enum(['answer_question', 'create_sentence']);
export type ExerciseType = z.infer<typeof exerciseTypeSchemaZ>;

export const exerciseCategorySchemaZ = z.enum(['writing', 'reading', 'listening', 'speaking']);
export type ExerciseCategory = z.infer<typeof exerciseCategorySchemaZ>;

export const exerciseDataAnswerQuestionSchemaZ = z.object({
    question: z.string(),
});
export type ExerciseDataAnswerQuestion = z.infer<typeof exerciseDataAnswerQuestionSchemaZ>;

export const exerciseDataCreateSentenceSchemaZ = z.object({
    userInstruction: z.string(),
});
export type ExerciseDataCreateSentence = z.infer<typeof exerciseDataCreateSentenceSchemaZ>;

export const exerciseSchemaZ = z.object({
    question: z.string(),
    answer: z.string(),
    type: exerciseTypeSchemaZ,
    category: exerciseCategorySchemaZ,
    data: z.union([exerciseDataAnswerQuestionSchemaZ, exerciseDataCreateSentenceSchemaZ]).nullable(),
});
export type Exercise = z.infer<typeof exerciseSchemaZ>;
