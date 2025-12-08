import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { getExerciseSetsByUserIdQuery, getUserByEmail } from "@core/index";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Play, Trash2 } from "lucide-react";

export default async function ExercisesPage() {
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin?callbackUrl=${encodeURIComponent("/exercises")}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    const user = await getUserByEmail(session.user.email);

    if (!user) {
        redirect(signInUrl);
    }

    const exerciseSets = await getExerciseSetsByUserIdQuery(user._id);

    // Group by type
    const multipleChoiceSets = exerciseSets.filter((set) => set.type === 'multiple_choice');
    const sentenceCreationSets = exerciseSets.filter((set) => set.type === 'sentence_creation');

    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-5xl flex-col gap-8 px-4 py-10">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-3xl font-semibold">Exercises</h1>
                    <p className="mt-2 text-neutral-600">
                        Practice your language skills with interactive exercises.
                    </p>
                </div>
                <Button asChild>
                    <Link href="/exercises/new">Create new exercise set</Link>
                </Button>
            </div>

            {exerciseSets.length === 0 ? (
                <Card className="border-dashed border-neutral-300 shadow-none hover:shadow-none hover:translate-y-0 bg-neutral-50">
                    <div className="p-12 text-center text-neutral-500">
                        <p className="text-lg font-medium">You don&apos;t have any exercise sets yet.</p>
                        <p className="mt-2 text-sm">
                            Create an exercise set to start practicing your language skills.
                        </p>
                    </div>
                </Card>
            ) : (
                <div className="space-y-8">
                    {/* Multiple Choice Section */}
                    {multipleChoiceSets.length > 0 && (
                        <div>
                            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                                Multiple Choice
                                <Badge variant="teal">{multipleChoiceSets.length}</Badge>
                            </h2>
                            <div className="grid gap-4 md:grid-cols-2">
                                {multipleChoiceSets.map((set) => (
                                    <Card key={set._id}>
                                        <CardHeader className="flex flex-row items-start justify-between gap-4">
                                            <div className="space-y-1">
                                                <CardTitle className="text-base font-medium">
                                                    {set.title}
                                                </CardTitle>
                                            </div>
                                            <form action={`/api/exercise-sets/${set._id}`} method="post">
                                                <div className="flex gap-2">
                                                    <Button variant="destructive" size="icon-sm" type="submit">
                                                        <Trash2 className="size-4" />
                                                    </Button>
                                                    <Button asChild size="sm">
                                                        <Link href={`/exercises/${set._id}`}>
                                                            <Play></Play>
                                                        </Link>
                                                    </Button>
                                                </div>
                                            </form>
                                        </CardHeader>
                                        <CardContent className="flex flex-col gap-2 text-sm text-neutral-600">
                                            <p className="whitespace-pre-wrap leading-relaxed">
                                                {set.topic || "No topic available."}
                                            </p>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Sentence Creation Section */}
                    {sentenceCreationSets.length > 0 && (
                        <div>
                            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                                Sentence Creation
                                <Badge variant="teal">{sentenceCreationSets.length}</Badge>
                            </h2>
                            <div className="grid gap-4 md:grid-cols-2">
                                {sentenceCreationSets.map((set) => (
                                    <Card key={set._id}>
                                        <CardHeader className="flex flex-row items-start justify-between gap-4">
                                            <div className="space-y-1">
                                                <CardTitle className="text-base font-medium">
                                                    {set.title}
                                                </CardTitle>
                                            </div>
                                            <form action={`/api/exercise-sets/${set._id}`} method="post">
                                                <div className="flex gap-2">
                                                    <Button variant="destructive" size="icon-sm" type="submit">
                                                        <Trash2 className="size-4" />
                                                    </Button>
                                                    <Button asChild size="sm">
                                                        <Link href={`/exercises/${set._id}`}>
                                                            <Play></Play>
                                                        </Link>
                                                    </Button>
                                                </div>
                                            </form>
                                        </CardHeader>
                                        <CardContent className="flex flex-col gap-2 text-sm text-neutral-600">
                                            <p className="whitespace-pre-wrap leading-relaxed">
                                                {set.topic || "No topic available."}
                                            </p>
                                        </CardContent>
                                    </Card>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </section>
    );
}
