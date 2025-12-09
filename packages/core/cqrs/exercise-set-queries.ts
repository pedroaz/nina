import { connectDatabase } from "../database/database";
import { ExerciseSet, ExerciseSetModel } from "../entities/exercise-set";
import { ExerciseSubmission, ExerciseSubmissionModel } from "../entities/exercise-submission";
import { DatabaseError, ValidationError } from "../errors";

// Get all exercise sets for a user
export async function getExerciseSetsByUserIdQuery(userId: string): Promise<ExerciseSet[]> {
    if (!userId) {
        throw new ValidationError('User ID is required');
    }

    try {
        await connectDatabase();
        return await ExerciseSetModel.find({
            'studentData.userId': userId,
        })
            .sort({ createdAt: -1 })
            .exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch exercise sets for user: ${userId}`, error);
    }
}

// Get a specific exercise set by ID
export async function getExerciseSetByIdQuery(setId: string): Promise<ExerciseSet | null> {
    if (!setId) {
        throw new ValidationError('Set ID is required');
    }

    try {
        await connectDatabase();
        return await ExerciseSetModel.findById(setId).exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch exercise set: ${setId}`, error);
    }
}

// Get all submissions for a specific exercise set and user
export async function getExerciseSubmissionsBySetAndUserQuery(
    setId: string,
    userId: string
): Promise<ExerciseSubmission[]> {
    if (!setId) {
        throw new ValidationError('Set ID is required');
    }
    if (!userId) {
        throw new ValidationError('User ID is required');
    }

    try {
        await connectDatabase();
        return await ExerciseSubmissionModel.find({
            exerciseSetId: setId,
            userId: userId,
        })
            .sort({ createdAt: -1 })
            .exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch submissions for set ${setId} and user ${userId}`, error);
    }
}

// Get a specific submission
export async function getExerciseSubmissionQuery(
    setId: string,
    userId: string,
    exerciseId: string
): Promise<ExerciseSubmission | null> {
    if (!setId) {
        throw new ValidationError('Set ID is required');
    }
    if (!userId) {
        throw new ValidationError('User ID is required');
    }
    if (!exerciseId) {
        throw new ValidationError('Exercise ID is required');
    }

    try {
        await connectDatabase();
        return await ExerciseSubmissionModel.findOne({
            exerciseSetId: setId,
            userId: userId,
            exerciseId: exerciseId,
        })
            .sort({ createdAt: -1 })
            .limit(1)
            .exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch submission for exercise ${exerciseId}`, error);
    }
}

// Get exercise sets by type
export async function getExerciseSetsByTypeQuery(
    userId: string,
    type: 'multiple_choice' | 'sentence_creation'
): Promise<ExerciseSet[]> {
    if (!userId) {
        throw new ValidationError('User ID is required');
    }
    if (!type) {
        throw new ValidationError('Type is required');
    }

    try {
        await connectDatabase();
        return await ExerciseSetModel.find({
            'studentData.userId': userId,
            type: type,
        })
            .sort({ createdAt: -1 })
            .exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch exercise sets of type ${type} for user ${userId}`, error);
    }
}

// Get exercise sets created from a specific lesson
export async function getExerciseSetsByLessonIdQuery(
    userId: string,
    lessonId: string
): Promise<ExerciseSet[]> {
    if (!userId) {
        throw new ValidationError('User ID is required');
    }
    if (!lessonId) {
        throw new ValidationError('Lesson ID is required');
    }

    try {
        await connectDatabase();
        return await ExerciseSetModel.find({
            'studentData.userId': userId,
            sourceLesson: lessonId,
        })
            .sort({ createdAt: -1 })
            .exec();
    } catch (error) {
        throw new DatabaseError(`Failed to fetch exercise sets for lesson ${lessonId}`, error);
    }
}
