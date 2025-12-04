import mongoose from 'mongoose';
import { z } from 'zod';
import { studentDataSchemaZ, studentSchemaM } from './student';

export const missionDifficultyZ = z.enum(['A1', 'A2', 'B1', 'B2', 'C1', 'C2']);

export type MissionDifficulty = z.infer<typeof missionDifficultyZ>;

export const missionSchemaZ = z.object({
    _id: z.string(),
    __v: z.number(),
    title: z.string(),
    scenario: z.string(),
    difficulty: missionDifficultyZ,
    objectives: z.array(z.string()),
    studentData: studentDataSchemaZ,
    createdAt: z.date(),
});

export type Mission = z.infer<typeof missionSchemaZ>;

export const missionSchema = new mongoose.Schema<Mission>({
    title: { type: String, required: true },
    scenario: { type: String, required: true },
    difficulty: { type: String, required: true, enum: ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'] },
    objectives: [{ type: String, required: true }],
    studentData: studentSchemaM,
    createdAt: { type: Date, required: true, default: Date.now },
});

export const MissionModel =
    (mongoose.models.missions as mongoose.Model<Mission> | undefined) ??
    mongoose.model<Mission>('missions', missionSchema);
