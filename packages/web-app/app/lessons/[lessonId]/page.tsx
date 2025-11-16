import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { Button } from "@/components/ui/button";
import { DualLanguageTextCard, type DualLanguageContent } from "@/components/dual-language-text-card";
import { AvatarHelper } from "@/components/avatar-helper";
import { ExtraSectionsInput } from "@/components/extra-sections-input";
import { GenerateFlashCardsDialog } from "@/components/generate-flashcards-dialog";
import { GenerateExercisesDialog } from "@/components/generate-exercises-dialog";
import { LessonMetadataDialog } from "@/components/lesson-metadata-dialog";
import { getLessonById, getUserByEmail } from "@core/index";

type LessonPageProps = {
    params: Promise<{
        lessonId: string;
    }>;
};

export default async function LessonDetailsPage({ params }: LessonPageProps) {
    const { lessonId } = await params;
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin?callbackUrl=${encodeURIComponent(`/lessons/${lessonId}`)}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        redirect(signInUrl);
    }

    const lesson = await getLessonById(lessonId);

    if (!lesson) {
        notFound();
    }

    const sanitizeDualLanguage = <T extends Partial<Record<"base" | "target", unknown>>>(
        entry: T | null | undefined,
    ): DualLanguageContent => {
        if (!entry) return {};

        const base = typeof entry.base === "string" ? entry.base : undefined;
        const target = typeof entry.target === "string" ? entry.target : undefined;

        return { base, target };
    };

    const sanitizeDualLanguageList = (
        entries: Array<Partial<Record<"base" | "target", unknown>>> | null | undefined,
    ): DualLanguageContent[] => {
        if (!Array.isArray(entries)) return [];
        return entries.map((entry) => sanitizeDualLanguage(entry));
    };

    const sanitizedLesson = {
        title: sanitizeDualLanguage(lesson.title),
        quickSummary: sanitizeDualLanguage(lesson.quickSummary),
        quickExamples: sanitizeDualLanguageList(lesson.quickExamples),
        fullExplanation: sanitizeDualLanguage(lesson.fullExplanation),
        extraSections: sanitizeDualLanguageList(lesson.extraSections),
    };

    // Convert lesson to plain object for client component
    // Use JSON serialization to strip MongoDB types (ObjectId, Date, etc.)
    const plainLesson = JSON.parse(JSON.stringify({
        _id: lesson._id.toString(),
        __v: lesson.__v,
        topic: lesson.topic,
        vocabulary: lesson.vocabulary,
        studentData: lesson.studentData,
        title: lesson.title,
        quickSummary: lesson.quickSummary,
        quickExamples: lesson.quickExamples,
        fullExplanation: lesson.fullExplanation,
    }));

    const lessonTitleRaw =
        sanitizedLesson.title.base || sanitizedLesson.title.target || "Untitled lesson";
    const lessonTitle = lessonTitleRaw.replace(/^#+\s*/, "").trimStart();

    return (
        <>
            <section className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-4 py-10">
                <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="space-y-2">
                        <h1 className="text-3xl font-semibold">{lessonTitle}</h1>
                        {lesson.vocabulary && (
                            <p className="text-sm text-slate-500">Vocabulary focus: {lesson.vocabulary}</p>
                        )}
                    </div>
                    <div className="flex gap-2">
                        <LessonMetadataDialog lessonId={lessonId} />
                        <GenerateFlashCardsDialog
                            lessonId={lessonId}
                            lessonTitle={lessonTitle}
                        />
                        <GenerateExercisesDialog
                            lessonId={lessonId}
                            lessonTitle={lessonTitle}
                        />
                        <Button variant="outline" asChild>
                            <Link href="/lessons">Back to lessons</Link>
                        </Button>
                    </div>
                </header>

                <article className="space-y-8">
                    <DualLanguageTextCard
                        heading="Summary"
                        content={sanitizedLesson.quickSummary}
                        emptyMessage="This lesson does not have a summary yet."
                    />

                    <DualLanguageTextCard
                        heading="Examples"
                        content={sanitizedLesson.quickExamples}
                        emptyMessage="This lesson does not have examples yet."
                    />

                    <DualLanguageTextCard
                        heading="Detailed Explanation"
                        content={sanitizedLesson.fullExplanation}
                        emptyMessage="This lesson does not have a detailed explanation yet."
                    />

                    <ExtraSectionsInput
                        lessonId={lessonId}
                        initialExtraSections={sanitizedLesson.extraSections}
                    />
                </article>
            </section>

            <AvatarHelper lesson={plainLesson} />
        </>
    );
}
