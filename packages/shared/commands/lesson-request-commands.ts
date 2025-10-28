import { connectDatabase } from "../database/database";
import { LessonRequest, LessonRequestModel, LessonRequestStatus } from "../entities/lesson_request";
import { publishLessonRequestCreated } from "../redis/lesson-request-stream";

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

    try {
        await publishLessonRequestCreated(lessonRequest);
    } catch (error) {
        console.error("Failed to publish lesson request creation event", error);
    }

    return lessonRequest;
}
