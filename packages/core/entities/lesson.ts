import mongoose from 'mongoose';
import { studentDataSchemaZ, studentSchemaM } from './student';
import { z } from 'zod';
import { dualLanguageSchemaM, dualLanguageSchemaZ } from './base';



export const lessonSchemaZ = z.object({
    _id: z.string(),
    __v: z.number(),
    topic: z.string(),
    vocabulary: z.string().optional(),
    studentData: studentDataSchemaZ,
    title: dualLanguageSchemaZ,
    quickSummary: dualLanguageSchemaZ,
    quickExamples: z.array(dualLanguageSchemaZ),
    fullExplanation: dualLanguageSchemaZ,
    extraSections: z.array(dualLanguageSchemaZ).optional(),
});

export type Lesson = z.infer<typeof lessonSchemaZ>;

export const lessonSchema = new mongoose.Schema<Lesson>({
    topic: { type: String, required: true },
    vocabulary: { type: String, required: false },
    studentData: studentSchemaM,
    title: dualLanguageSchemaM,
    quickSummary: dualLanguageSchemaM,
    quickExamples: [dualLanguageSchemaM],
    fullExplanation: dualLanguageSchemaM,
    extraSections: [dualLanguageSchemaM],
});

export const LessonModel =
    (mongoose.models.lessons as mongoose.Model<Lesson> | undefined) ??
    mongoose.model<Lesson>('lessons', lessonSchema);