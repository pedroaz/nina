import mongoose from 'mongoose';

export interface LessonRequest extends mongoose.Document {
    creatorId: string;
    prompt: string;
    lessonId: string | null;
    status: LessonRequestStatus;
    createdAt: Date;
    updatedAt: Date;
}

export enum LessonRequestStatus {
    Requested = "requested",
    Approved = "done"
}

export const lessonRequestSchema = new mongoose.Schema({
    creatorId: { type: String, required: true, index: true },
    prompt: { type: String, required: true },
    lessonId: { type: String, default: null },
    status: {
        type: String,
        enum: Object.values(LessonRequestStatus),
        default: LessonRequestStatus.Requested,
    },
}, { timestamps: true });

export const LessonRequestModel =
    (mongoose.models.lesson_requests as mongoose.Model<LessonRequest> | undefined) ??
    mongoose.model<LessonRequest>('lesson_requests', lessonRequestSchema);