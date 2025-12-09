import mongoose from 'mongoose';
import { z } from 'zod';

// Exercise Submission schema - tracks user answers and scoring
export const exerciseSubmissionSchemaZ = z.object({
    _id: z.string(),
    __v: z.number(),
    exerciseSetId: z.string(),
    userId: z.string(),
    exerciseId: z.string(), // ID of the specific exercise within the set
    userAnswer: z.string(), // For MC: index as string, for sentence: the full sentence
    score: z.number().min(0).max(100), // For MC: 0 or 100, for sentence: 0-100
    feedback: z.string().optional(), // AI explanation (especially for sentence creation)
    createdAt: z.date(),
    updatedAt: z.date(),
});

export type ExerciseSubmission = z.infer<typeof exerciseSubmissionSchemaZ>;

export const exerciseSubmissionSchema = new mongoose.Schema<ExerciseSubmission>({
    exerciseSetId: { type: String, required: true, index: true },
    userId: { type: String, required: true, index: true },
    exerciseId: { type: String, required: true },
    userAnswer: { type: String, required: true },
    score: { type: Number, required: true, min: 0, max: 100 },
    feedback: { type: String, required: false },
}, {
    timestamps: true,
});

// Compound index for efficient lookups
exerciseSubmissionSchema.index({ exerciseSetId: 1, userId: 1 });
exerciseSubmissionSchema.index({ exerciseSetId: 1, userId: 1, exerciseId: 1 });

export const ExerciseSubmissionModel =
    (mongoose.models.exerciseSubmissions as mongoose.Model<ExerciseSubmission> | undefined) ??
    mongoose.model<ExerciseSubmission>('exerciseSubmissions', exerciseSubmissionSchema);
