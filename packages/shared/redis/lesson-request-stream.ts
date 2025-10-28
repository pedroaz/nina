import { LessonRequest } from "../entities/lesson_request";
import { appendToStream } from "./redis";

const LESSON_REQUEST_STREAM_KEY = "lesson-request-events";
const LESSON_REQUEST_CREATED_EVENT = "lesson-request.created";

export async function publishLessonRequestCreated(
    lessonRequest: LessonRequest,
): Promise<string> {
    return appendToStream(LESSON_REQUEST_STREAM_KEY, {
        event: LESSON_REQUEST_CREATED_EVENT,
        payload: JSON.stringify(lessonRequest),
    });
}
