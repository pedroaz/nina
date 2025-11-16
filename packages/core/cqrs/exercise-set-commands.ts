import { connectDatabase } from "../database/database";
import {
    ExerciseSet,
    ExerciseSetModel,
    MultipleChoiceExercise,
    SentenceCreationExercise,
} from "../entities/exercise-set";
import { ExerciseSubmission, ExerciseSubmissionModel } from "../entities/exercise-submission";
import { getUserById } from "./user-queries";
import { getLessonById } from "./lesson-queries";
import {
    generateMultipleChoiceFromPromptFlow,
    generateMultipleChoiceFromLessonFlow,
    generateSentenceCreationFromPromptFlow,
    generateSentenceCreationFromLessonFlow,
    judgeSentenceFlow,
} from "../llm/llm";
import { savePromptMetadataCommand } from "./prompt-metadata-commands";

// Manual creation of exercise sets
export interface CreateExerciseSetRequestData {
    userId: string;
    title: string;
    topic: string;
    type: 'multiple_choice' | 'sentence_creation';
    exercises: MultipleChoiceExercise[] | SentenceCreationExercise[];
    sourceLesson?: string;
}

export async function createExerciseSetCommand(
    data: CreateExerciseSetRequestData,
): Promise<ExerciseSet> {
    await connectDatabase();
    const user = await getUserById(data.userId);

    if (!user) throw new Error('User not found');

    const setObject = new ExerciseSetModel({
        title: data.title,
        topic: data.topic,
        type: data.type,
        studentData: {
            userId: user._id,
            userName: user.name,
            preferredLanguage: user.baseLanguage,
            studentLevel: user.level,
        },
        exercises: data.exercises,
        sourceLesson: data.sourceLesson,
    });

    await setObject.save();
    return setObject;
}

// Generate multiple choice exercises from prompt
export interface GenerateMultipleChoiceFromPromptRequestData {
    userId: string;
    topic: string;
    exerciseCount: number;
}

export async function generateMultipleChoiceFromPromptCommand(
    data: GenerateMultipleChoiceFromPromptRequestData,
): Promise<ExerciseSet> {
    await connectDatabase();
    const user = await getUserById(data.userId);

    if (!user) throw new Error('User not found');

    // Generate exercises using LLM
    const { output: llmResult, usage } = await generateMultipleChoiceFromPromptFlow({
        topic: data.topic,
        exerciseCount: data.exerciseCount,
        studentLevel: user.level,
        baseLanguage: user.baseLanguage,
        targetLanguage: user.targetLanguage,
    });

    if (!llmResult || !llmResult.exercises || llmResult.exercises.length === 0) {
        throw new Error('Failed to generate multiple choice exercises');
    }

    // Create exercise set with generated exercises
    const setObject = new ExerciseSetModel({
        title: llmResult.title,
        topic: data.topic,
        type: 'multiple_choice',
        studentData: {
            userId: user._id,
            userName: user.name,
            preferredLanguage: user.baseLanguage,
            studentLevel: user.level,
        },
        exercises: llmResult.exercises,
    });

    await setObject.save();

    // Save prompt metadata
    await savePromptMetadataCommand({
        operation: 'exercise_generation_mc',
        modelUsed: usage.modelUsed as 'gpt-5-nano' | 'gpt-4o-mini',
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        totalTokens: usage.totalTokens,
        userId: user._id.toString(),
        executionTimeMs: usage.executionTimeMs,
        finishReason: usage.finishReason,
    });

    return setObject;
}

// Generate multiple choice exercises from lesson
export interface GenerateMultipleChoiceFromLessonRequestData {
    userId: string;
    lessonId: string;
    exerciseCount: number;
    setTitle: string;
}

export async function generateMultipleChoiceFromLessonCommand(
    data: GenerateMultipleChoiceFromLessonRequestData,
): Promise<ExerciseSet> {
    await connectDatabase();
    const user = await getUserById(data.userId);
    if (!user) throw new Error('User not found');

    const lesson = await getLessonById(data.lessonId);
    if (!lesson) throw new Error('Lesson not found');

    // Serialize lesson for LLM
    const serializedLesson = {
        _id: lesson._id.toString(),
        __v: lesson.__v,
        topic: lesson.topic,
        vocabulary: lesson.vocabulary || '',
        studentData: {
            userId: lesson.studentData.userId.toString(),
            userName: lesson.studentData.userName,
            preferredLanguage: lesson.studentData.preferredLanguage,
            studentLevel: lesson.studentData.studentLevel,
        },
        title: lesson.title,
        quickSummary: lesson.quickSummary,
        quickExamples: lesson.quickExamples,
        fullExplanation: lesson.fullExplanation,
        extraSections: lesson.extraSections || [],
    };

    // Generate exercises using LLM
    const { output: llmResult, usage } = await generateMultipleChoiceFromLessonFlow({
        lesson: serializedLesson,
        exerciseCount: data.exerciseCount,
        studentLevel: user.level,
        baseLanguage: user.baseLanguage,
        targetLanguage: user.targetLanguage,
    });

    if (!llmResult || !llmResult.exercises || llmResult.exercises.length === 0) {
        throw new Error('Failed to generate multiple choice exercises from lesson');
    }

    // Create exercise set
    const setObject = new ExerciseSetModel({
        title: data.setTitle,
        topic: lesson.topic,
        type: 'multiple_choice',
        studentData: {
            userId: user._id,
            userName: user.name,
            preferredLanguage: user.baseLanguage,
            studentLevel: user.level,
        },
        exercises: llmResult.exercises,
        sourceLesson: data.lessonId,
    });

    await setObject.save();

    // Save prompt metadata
    await savePromptMetadataCommand({
        lessonId: data.lessonId,
        operation: 'exercise_generation_mc',
        modelUsed: usage.modelUsed as 'gpt-5-nano' | 'gpt-4o-mini',
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        totalTokens: usage.totalTokens,
        userId: user._id.toString(),
        executionTimeMs: usage.executionTimeMs,
        finishReason: usage.finishReason,
    });

    return setObject;
}

// Generate sentence creation exercises from prompt
export interface GenerateSentenceCreationFromPromptRequestData {
    userId: string;
    topic: string;
    exerciseCount: number;
}

export async function generateSentenceCreationFromPromptCommand(
    data: GenerateSentenceCreationFromPromptRequestData,
): Promise<ExerciseSet> {
    await connectDatabase();
    const user = await getUserById(data.userId);

    if (!user) throw new Error('User not found');

    // Generate exercises using LLM
    const { output: llmResult, usage } = await generateSentenceCreationFromPromptFlow({
        topic: data.topic,
        exerciseCount: data.exerciseCount,
        studentLevel: user.level,
        baseLanguage: user.baseLanguage,
        targetLanguage: user.targetLanguage,
    });

    if (!llmResult || !llmResult.exercises || llmResult.exercises.length === 0) {
        throw new Error('Failed to generate sentence creation exercises');
    }

    // Create exercise set with generated exercises
    const setObject = new ExerciseSetModel({
        title: llmResult.title,
        topic: data.topic,
        type: 'sentence_creation',
        studentData: {
            userId: user._id,
            userName: user.name,
            preferredLanguage: user.baseLanguage,
            studentLevel: user.level,
        },
        exercises: llmResult.exercises,
    });

    await setObject.save();

    // Save prompt metadata
    await savePromptMetadataCommand({
        operation: 'exercise_generation_sc',
        modelUsed: usage.modelUsed as 'gpt-5-nano' | 'gpt-4o-mini',
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        totalTokens: usage.totalTokens,
        userId: user._id.toString(),
        executionTimeMs: usage.executionTimeMs,
        finishReason: usage.finishReason,
    });

    return setObject;
}

// Generate sentence creation exercises from lesson
export interface GenerateSentenceCreationFromLessonRequestData {
    userId: string;
    lessonId: string;
    exerciseCount: number;
    setTitle: string;
}

export async function generateSentenceCreationFromLessonCommand(
    data: GenerateSentenceCreationFromLessonRequestData,
): Promise<ExerciseSet> {
    await connectDatabase();
    const user = await getUserById(data.userId);
    if (!user) throw new Error('User not found');

    const lesson = await getLessonById(data.lessonId);
    if (!lesson) throw new Error('Lesson not found');

    // Serialize lesson for LLM
    const serializedLesson = {
        _id: lesson._id.toString(),
        __v: lesson.__v,
        topic: lesson.topic,
        vocabulary: lesson.vocabulary || '',
        studentData: {
            userId: lesson.studentData.userId.toString(),
            userName: lesson.studentData.userName,
            preferredLanguage: lesson.studentData.preferredLanguage,
            studentLevel: lesson.studentData.studentLevel,
        },
        title: lesson.title,
        quickSummary: lesson.quickSummary,
        quickExamples: lesson.quickExamples,
        fullExplanation: lesson.fullExplanation,
        extraSections: lesson.extraSections || [],
    };

    // Generate exercises using LLM
    const { output: llmResult, usage } = await generateSentenceCreationFromLessonFlow({
        lesson: serializedLesson,
        exerciseCount: data.exerciseCount,
        studentLevel: user.level,
        baseLanguage: user.baseLanguage,
        targetLanguage: user.targetLanguage,
    });

    if (!llmResult || !llmResult.exercises || llmResult.exercises.length === 0) {
        throw new Error('Failed to generate sentence creation exercises from lesson');
    }

    // Create exercise set
    const setObject = new ExerciseSetModel({
        title: data.setTitle,
        topic: lesson.topic,
        type: 'sentence_creation',
        studentData: {
            userId: user._id,
            userName: user.name,
            preferredLanguage: user.baseLanguage,
            studentLevel: user.level,
        },
        exercises: llmResult.exercises,
        sourceLesson: data.lessonId,
    });

    await setObject.save();

    // Save prompt metadata
    await savePromptMetadataCommand({
        lessonId: data.lessonId,
        operation: 'exercise_generation_sc',
        modelUsed: usage.modelUsed as 'gpt-5-nano' | 'gpt-4o-mini',
        inputTokens: usage.inputTokens,
        outputTokens: usage.outputTokens,
        totalTokens: usage.totalTokens,
        userId: user._id.toString(),
        executionTimeMs: usage.executionTimeMs,
        finishReason: usage.finishReason,
    });

    return setObject;
}

// Submit exercise answer
export interface SubmitExerciseAnswerRequestData {
    userId: string;
    exerciseSetId: string;
    exerciseId: string;
    userAnswer: string;
}

export interface SubmitExerciseAnswerResult {
    submission: ExerciseSubmission;
    isCorrect?: boolean; // For multiple choice
    score?: number; // For sentence creation (0-100)
    feedback?: string; // For sentence creation
}

export async function submitExerciseAnswerCommand(
    data: SubmitExerciseAnswerRequestData,
): Promise<SubmitExerciseAnswerResult> {
    await connectDatabase();

    const user = await getUserById(data.userId);
    if (!user) throw new Error('User not found');

    const exerciseSet = await ExerciseSetModel.findById(data.exerciseSetId).exec();
    if (!exerciseSet) throw new Error('Exercise set not found');

    // Find the specific exercise
    let exercise: any;
    let exerciseIndex: number;

    // Check if using index-based ID (for backward compatibility with old data)
    if (data.exerciseId.startsWith('index_')) {
        exerciseIndex = parseInt(data.exerciseId.replace('index_', ''), 10);
        exercise = exerciseSet.exercises[exerciseIndex];
    } else {
        // Find by _id
        exerciseIndex = exerciseSet.exercises.findIndex((ex: any) => ex._id && ex._id.toString() === data.exerciseId);
        exercise = exerciseIndex >= 0 ? exerciseSet.exercises[exerciseIndex] : null;
    }

    if (!exercise) throw new Error('Exercise not found');

    let score: number;
    let feedback: string | undefined;
    let isCorrect: boolean | undefined;

    if (exerciseSet.type === 'multiple_choice') {
        // For multiple choice: check if answer matches correctOptionIndex
        const mcExercise = exercise as any;
        const userAnswerIndex = parseInt(data.userAnswer, 10);
        isCorrect = userAnswerIndex === mcExercise.correctOptionIndex;
        score = isCorrect ? 100 : 0;
        feedback = undefined;
    } else if (exerciseSet.type === 'sentence_creation') {
        // For sentence creation: use LLM to judge
        const scExercise = exercise as any;
        const { output: judgeResult, usage } = await judgeSentenceFlow({
            prompt: scExercise.prompt.target,
            promptBase: scExercise.prompt.base,
            referenceAnswer: scExercise.referenceAnswer,
            context: scExercise.context,
            userAnswer: data.userAnswer,
            studentLevel: user.level,
            baseLanguage: user.baseLanguage,
            targetLanguage: user.targetLanguage,
        });

        if (!judgeResult) throw new Error('Failed to judge sentence');

        score = judgeResult.score;
        feedback = judgeResult.feedback;

        // Save prompt metadata for judging
        await savePromptMetadataCommand({
            operation: 'exercise_sentence_judging',
            modelUsed: usage.modelUsed as 'gpt-5-nano' | 'gpt-4o-mini',
            inputTokens: usage.inputTokens,
            outputTokens: usage.outputTokens,
            totalTokens: usage.totalTokens,
            userId: user._id.toString(),
            executionTimeMs: usage.executionTimeMs,
            finishReason: usage.finishReason,
        });
    } else {
        throw new Error('Unknown exercise type');
    }

    // Save submission
    const submission = new ExerciseSubmissionModel({
        exerciseSetId: data.exerciseSetId,
        userId: data.userId,
        exerciseId: data.exerciseId,
        userAnswer: data.userAnswer,
        score,
        feedback,
    });

    await submission.save();

    return {
        submission,
        isCorrect,
        score,
        feedback,
    };
}

// Delete exercise set
export interface DeleteExerciseSetRequestData {
    setId: string;
}

export async function deleteExerciseSetCommand(
    data: DeleteExerciseSetRequestData,
): Promise<void> {
    await connectDatabase();
    await ExerciseSetModel.deleteOne({
        _id: data.setId,
    }).exec();

    // Also delete all submissions for this set
    await ExerciseSubmissionModel.deleteMany({
        exerciseSetId: data.setId,
    }).exec();
}
