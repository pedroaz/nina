import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { Button } from "@/components/ui/button";
import { DualLanguageTextCard, type DualLanguageContent } from "@/components/dual-language-text-card";
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

    const sanitizeDualLanguage = <T extends Partial<Record<"base" | "german", unknown>>>(
        entry: T | null | undefined,
    ): DualLanguageContent => {
        if (!entry) return {};

        const base = typeof entry.base === "string" ? entry.base : undefined;
        const german = typeof entry.german === "string" ? entry.german : undefined;

        return { base, german };
    };

    const sanitizeDualLanguageList = (
        entries: Array<Partial<Record<"base" | "german", unknown>>> | null | undefined,
    ): DualLanguageContent[] => {
        if (!Array.isArray(entries)) return [];
        return entries.map((entry) => sanitizeDualLanguage(entry));
    };

    const sanitizedLesson = {
        title: sanitizeDualLanguage(lesson.title),
        quickSummary: sanitizeDualLanguage(lesson.quickSummary),
        quickExamples: sanitizeDualLanguageList(lesson.quickExamples),
        fullExplanation: sanitizeDualLanguage(lesson.fullExplanation),
    };

    const lessonTitleRaw =
        sanitizedLesson.title.base || sanitizedLesson.title.german || "Untitled lesson";
    const lessonTitle = lessonTitleRaw.replace(/^#+\s*/, "").trimStart();

    return (
        <section className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-4 py-10">
            <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-2">
                    <h1 className="text-3xl font-semibold">{lessonTitle}</h1>
                    {lesson.vocabulary && (
                        <p className="text-sm text-slate-500">Vocabulary focus: {lesson.vocabulary}</p>
                    )}
                </div>
                <Button variant="outline" asChild>
                    <Link href="/lessons">Back to lessons</Link>
                </Button>
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
            </article>
        </section>
    );
}
