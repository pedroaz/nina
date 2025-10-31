import Link from "next/link";
import { redirect, notFound } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { Button } from "@/components/ui/button";
import { getLessonById, getLessonsByUserId, getUserByEmail } from "@core/index";

type LessonPageProps = {
    params: {
        lessonId: string;
    };
};

function formatLabel(value: string | undefined | null) {
    if (!value) return "";

    return value
        .split("_")
        .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
        .join(" ");
}

export default async function LessonDetailsPage({ params }: LessonPageProps) {
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin?callbackUrl=${encodeURIComponent(`/lessons/${params.lessonId}`)}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        redirect(signInUrl);
    }

    const lesson = await getLessonById(params.lessonId);

    if (!lesson) {
        notFound();
    }

    // const englishContent = lesson.englishContent?.trim();
    const germanContent = lesson.germanContent?.trim();
    const exercises = Array.isArray(lesson.exercises) ? lesson.exercises : [];

    return (
        <section className="mx-auto flex w-full max-w-4xl flex-col gap-8 px-4 py-10">
            <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-2">
                    <p className="text-sm text-slate-500">Custom lesson</p>
                    <h1 className="text-3xl font-semibold">
                        {lesson.title || "Untitled lesson"}
                    </h1>
                </div>
                <Button variant="outline" asChild>
                    <Link href="/lessons">Back to lessons</Link>
                </Button>
            </header>

            <article className="space-y-8">
                <section className="space-y-3">
                    <h2 className="text-xl font-semibold">English content</h2>
                    <p className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-white/70 p-4 text-slate-700">
                        {englishContent || "This lesson does not have English content yet."}
                    </p>
                </section>

                <section className="space-y-3">
                    <h2 className="text-xl font-semibold">German content</h2>
                    <p className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-white/70 p-4 text-slate-700">
                        {germanContent || "This lesson does not have German content yet."}
                    </p>
                </section>

                {exercises.length > 0 && (
                    <section className="space-y-4">
                        <h2 className="text-xl font-semibold">Exercises</h2>
                        <div className="space-y-3">
                            {exercises.map((exercise, index) => (
                                <div
                                    key={`${exercise.question ?? "exercise"}-${index}`}
                                    className="rounded-lg border border-slate-200 p-4"
                                >
                                    {(exercise.category || exercise.type) && (
                                        <p className="text-xs uppercase text-slate-500">
                                            {[
                                                formatLabel(exercise.category),
                                                formatLabel(exercise.type),
                                            ]
                                                .filter(Boolean)
                                                .join(" • ")}
                                        </p>
                                    )}
                                    {exercise.question && (
                                        <p className="mt-2 text-base font-medium text-slate-800">
                                            {exercise.question}
                                        </p>
                                    )}
                                    {exercise.answer && (
                                        <p className="mt-2 text-sm text-slate-600">
                                            Suggested answer: {exercise.answer}
                                        </p>
                                    )}
                                </div>
                            ))}
                        </div>
                    </section>
                )}
            </article>
        </section>
    );
}
