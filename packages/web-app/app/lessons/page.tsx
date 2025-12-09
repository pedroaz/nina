import Link from "next/link";
import { Suspense } from "react";
import { getLessonsByUserId } from "@core/index";
import { Button } from "@/components/ui/button";
import { PentagonSpinner } from "@/components/pentagon-spinner";
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Trash2, Play } from "lucide-react";

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

export default function CustomLessons() {
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
            <Suspense fallback={<PentagonSpinner />}>
                <LessonList />
            </Suspense>
        </section>
    );
}

async function LessonList() {
    const { getAuthenticatedUser } = await import("@/lib/get-authenticated-user");
    const user = await getAuthenticatedUser("/lessons");

    const lessons = await getLessonsByUserId(user._id);

    const lessonItems: LessonListItem[] = lessons.map((request) => ({
        id: request._id.toString(),
        title: request.title?.base ?? "Untitled lesson",
        topic: request.topic,
        vocabulary: request.vocabulary ?? "",
    }));

    if (lessonItems.length === 0) {
        return (
            <Card className="border-dashed border-neutral-300 shadow-none hover:shadow-none hover:translate-y-0 bg-neutral-50">
                <div className="p-12 text-center text-neutral-500">
                    <p className="text-lg font-medium">You have not submitted any lesson requests yet.</p>
                    <p className="mt-2 text-sm">
                        Share what you want to learn and we will create a lesson for you.
                    </p>
                </div>
            </Card>
        );
    }

    return (
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
                            <div className="flex gap-2">
                                <Button variant="destructive" size="icon-sm" type="submit">
                                    <Trash2 className="size-4" />
                                </Button>
                                <Button asChild size="sm">
                                    <Link href={`/lessons/${lesson.id}`}>
                                        <Play></Play>
                                    </Link>
                                </Button>
                            </div>
                        </form>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-2 text-sm text-neutral-600">
                        <p className="whitespace-pre-wrap leading-relaxed">
                            {lesson.topic}
                        </p>
                    </CardContent>
                </Card>
            ))}
        </div>
    );
}
