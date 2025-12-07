import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { getLessonsByUserId, getUserByEmail } from "@core/index";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";

type LessonListItem = {
    id: string;
    title: string;
    topic: string;
    vocabulary: string;
};

function formatCreatedAt(dateIso: string | null) {
    if (!dateIso) {
        return "Unknown";
    }

    return new Date(dateIso).toLocaleString();
}

export default async function CustomLessons() {
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin?callbackUrl=${encodeURIComponent("/lessons")}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        redirect(signInUrl);
    }

    const lessons = await getLessonsByUserId(user._id);

    const lessonItems: LessonListItem[] = lessons.map((request) => ({
        id: request._id.toString(),
        title: request.title?.base ?? "Untitled lesson",
        topic: request.topic,
        vocabulary: request.vocabulary ?? "",
    }));

    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-5xl flex-col gap-8 px-4 py-10">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-3xl font-semibold">Lessons</h1>
                </div>
                <Button asChild>
                    <Link href="/lessons/new">Create new</Link>
                </Button>
            </div>

            {lessonItems.length === 0 ? (
                <div className="rounded-xl border border-dashed border-neutral-200 p-12 text-center text-neutral-500">
                    <p>You have not submitted any lesson requests yet.</p>
                    <p className="mt-2 text-sm">
                        Share what you want to learn and we will create a lesson for you.
                    </p>
                </div>
            ) : (
                <div className="grid gap-4 md:grid-cols-2">
                    {lessonItems.map((lesson) => (
                        <Card key={lesson.id}>
                            <CardHeader className="flex flex-row items-start justify-between gap-4">
                                <div className="space-y-1">
                                    <CardTitle className="text-base font-medium">
                                        {lesson.title}
                                    </CardTitle>
                                </div>
                                <form action={`/api/lessons/${lesson.id}`} method="post">
                                    <Button variant="destructive" size="sm" type="submit">
                                        Delete
                                    </Button>
                                </form>
                            </CardHeader>
                            <CardContent className="flex flex-col gap-2 text-sm text-neutral-600">
                                <p className="whitespace-pre-wrap leading-relaxed">
                                    {lesson.topic}
                                </p>
                            </CardContent>
                            <CardFooter className="flex justify-end">
                                <Button asChild size="sm">
                                    <Link href={`/lessons/${lesson.id}`}>Start lesson</Link>
                                </Button>
                            </CardFooter>
                        </Card>
                    ))}
                </div>
            )}
        </section>
    );
}
