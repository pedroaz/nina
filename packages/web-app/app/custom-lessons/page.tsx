import Link from "next/link";
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import {
    getLessonRequestsByCreatorId,
    getUserByEmail,
    LessonRequestStatus,
    deleteLessonRequestCommand,
} from "@shared/index";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";

type LessonRequestListItem = {
    id: string;
    prompt: string;
    status: LessonRequestStatus;
    lessonId: string | null;
    createdAt: string | null;
};

const STATUS_LABELS: Record<LessonRequestStatus, string> = {
    [LessonRequestStatus.Requested]: "Requested",
    [LessonRequestStatus.Approved]: "Approved",
};

function formatCreatedAt(dateIso: string | null) {
    if (!dateIso) {
        return "Unknown";
    }

    return new Date(dateIso).toLocaleString();
}

export default async function CustomLessons() {
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin?callbackUrl=${encodeURIComponent("/custom-lessons")}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        redirect(signInUrl);
    }

    const creatorId = user.id;

    const deleteLessonRequest = async (formData: FormData) => {
        "use server";
        const requestId = formData.get("requestId");

        if (typeof requestId !== "string") {
            return;
        }

        await deleteLessonRequestCommand({ requestId, creatorId });
        revalidatePath("/custom-lessons");
    };

    const lessonRequests = await getLessonRequestsByCreatorId(user.id);

    const requestItems: LessonRequestListItem[] = lessonRequests.map((request) => ({
        id: request.id,
        prompt: request.prompt,
        status: request.status,
        lessonId: request.lessonId,
        createdAt: request.createdAt?.toISOString?.() ?? null,
    }));

    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-5xl flex-col gap-8 px-4 py-10">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-3xl font-semibold">Custom Lessons</h1>
                </div>
                <Button asChild>
                    <Link href="/custom-lessons/new">Create new</Link>
                </Button>
            </div>

            {requestItems.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-200 p-12 text-center text-slate-500">
                    <p>You have not submitted any custom lesson requests yet.</p>
                    <p className="mt-2 text-sm">
                        Share what you want to learn and we will create a lesson for you.
                    </p>
                </div>
            ) : (
                <div className="grid gap-4 md:grid-cols-2">
                    {requestItems.map((request) => (
                        <Card key={request.id}>
                            <CardHeader className="flex flex-row items-start justify-between gap-4">
                                <div className="space-y-1">
                                    <CardTitle className="text-base font-medium">
                                        Custom lesson request
                                    </CardTitle>
                                    <CardDescription>
                                        Status: {STATUS_LABELS[request.status]}
                                    </CardDescription>
                                </div>
                                <form action={deleteLessonRequest} method="post">
                                    <input type="hidden" name="requestId" value={request.id} />
                                    <Button variant="outline" size="sm" type="submit">
                                        Delete
                                    </Button>
                                </form>
                            </CardHeader>
                            <CardContent className="flex flex-col gap-4 text-sm text-slate-600">
                                <p className="whitespace-pre-wrap leading-relaxed">
                                    {request.prompt}
                                </p>
                                <div className="text-xs text-slate-400">
                                    Created {formatCreatedAt(request.createdAt)}
                                </div>
                                {request.lessonId ? (
                                    <div className="text-xs text-slate-500">
                                        Linked lesson ID: {request.lessonId}
                                    </div>
                                ) : null}
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </section>
    );
}
