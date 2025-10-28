import { connectDatabase } from "../database/database";
import { type LessonRequest, LessonRequestModel, LessonRequestStatus } from "../entities/lesson_request";

export interface CreateLessonRequestData {
    creatorId: string;
    prompt: string;
    lessonId?: string | null;
}

export async function createLessonRequestCommand(
    data: CreateLessonRequestData,
): Promise<LessonRequest> {
    await connectDatabase();
    const lessonRequest = new LessonRequestModel({
        creatorId: data.creatorId,
        prompt: data.prompt,
        lessonId: data.lessonId ?? null,
        status: LessonRequestStatus.Requested,
    });

    await lessonRequest.save();
    return lessonRequest;
}
