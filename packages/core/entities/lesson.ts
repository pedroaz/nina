import mongoose from 'mongoose';

export interface Lesson extends mongoose.Document {
    creatorId: string;
    title: string;
    prompt: string;
    content: string;
    exercises: Exercise[];
}

export interface Exercise {
    question: string;
    answer: string;
    type: ExerciseType;
    category: ExerciseCategory;
    data: ExerciseDataAnswerQuestion | ExerciseDataCreateSentence | null;
}

export enum ExerciseType {
    AnswerQuestion = "answer_question",
    CreateSentence = "create_sentence",
}

export enum ExerciseCategory {
    Writing = "writing",
    Reading = "reading",
    Listening = "listening",
    Speaking = "speaking",
}

export interface ExerciseDataAnswerQuestion {
    question: string;
}

export interface ExerciseDataCreateSentence {
    prompt: string;
}

const exerciseSchema = new mongoose.Schema({
    question: String,
    answer: String,
    type: {
        type: String,
        enum: Object.values(ExerciseType),
    },
    category: {
        type: String,
        enum: Object.values(ExerciseCategory),
    },
    data: mongoose.Schema.Types.Mixed,
});

export const lessonSchema = new mongoose.Schema({
    creatorId: String,
    title: String,
    prompt: String,
    content: String,
    exercises: [exerciseSchema],
});

export const LessonModel =
    (mongoose.models.lessons as mongoose.Model<Lesson> | undefined) ??
    mongoose.model<Lesson>('lessons', lessonSchema);