import { connectDatabase } from "../database/database";
import { ExerciseSet, ExerciseSetModel } from "../entities/exercise-set";
import { ExerciseSubmission, ExerciseSubmissionModel } from "../entities/exercise-submission";

// Get all exercise sets for a user
export async function getExerciseSetsByUserIdQuery(userId: string): Promise<ExerciseSet[]> {
    await connectDatabase();
    const sets = await ExerciseSetModel.find({
        'studentData.userId': userId,
    })
        .sort({ createdAt: -1 })
        .exec();

    return sets;
}

// Get a specific exercise set by ID
export async function getExerciseSetByIdQuery(setId: string): Promise<ExerciseSet | null> {
    await connectDatabase();
    const set = await ExerciseSetModel.findById(setId).exec();
    return set;
}

// Get all submissions for a specific exercise set and user
export async function getExerciseSubmissionsBySetAndUserQuery(
    setId: string,
    userId: string
): Promise<ExerciseSubmission[]> {
    await connectDatabase();
    const submissions = await ExerciseSubmissionModel.find({
        exerciseSetId: setId,
        userId: userId,
    })
        .sort({ createdAt: -1 })
        .exec();

    return submissions;
}

// Get a specific submission
export async function getExerciseSubmissionQuery(
    setId: string,
    userId: string,
    exerciseId: string
): Promise<ExerciseSubmission | null> {
    await connectDatabase();
    const submission = await ExerciseSubmissionModel.findOne({
        exerciseSetId: setId,
        userId: userId,
        exerciseId: exerciseId,
    })
        .sort({ createdAt: -1 })
        .limit(1)
        .exec();

    return submission;
}

// Get exercise sets by type
export async function getExerciseSetsByTypeQuery(
    userId: string,
    type: 'multiple_choice' | 'sentence_creation'
): Promise<ExerciseSet[]> {
    await connectDatabase();
    const sets = await ExerciseSetModel.find({
        'studentData.userId': userId,
        type: type,
    })
        .sort({ createdAt: -1 })
        .exec();

    return sets;
}

// Get exercise sets created from a specific lesson
export async function getExerciseSetsByLessonIdQuery(
    userId: string,
    lessonId: string
): Promise<ExerciseSet[]> {
    await connectDatabase();
    const sets = await ExerciseSetModel.find({
        'studentData.userId': userId,
        sourceLesson: lessonId,
    })
        .sort({ createdAt: -1 })
        .exec();

    return sets;
}
