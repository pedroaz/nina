import Link from "next/link";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { getExerciseSetsByUserIdQuery, getUserByEmail } from "@core/index";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

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
                <div className="rounded-xl border border-dashed border-neutral-200 p-12 text-center text-neutral-500">
                    <p>You don&apos;t have any exercise sets yet.</p>
                    <p className="mt-2 text-sm">
                        Create an exercise set to start practicing your language skills.
                    </p>
                </div>
            ) : (
                <div className="space-y-8">
                    {/* Multiple Choice Section */}
                    {multipleChoiceSets.length > 0 && (
                        <div>
                            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                                Multiple Choice
                                <Badge variant="secondary">{multipleChoiceSets.length}</Badge>
                            </h2>
                            <div className="grid gap-4 md:grid-cols-2">
                                {multipleChoiceSets.map((set) => (
                                    <Link key={set._id} href={`/exercises/${set._id}`}>
                                        <Card className="hover:bg-neutral-50 transition-colors cursor-pointer">
                                            <CardHeader>
                                                <div className="flex items-start justify-between">
                                                    <div className="flex-1">
                                                        <CardTitle className="text-lg">{set.title}</CardTitle>
                                                        <CardDescription className="mt-1">
                                                            {set.topic}
                                                        </CardDescription>
                                                    </div>
                                                    <Badge variant="outline">MC</Badge>
                                                </div>
                                            </CardHeader>
                                            <CardContent>
                                                <p className="text-sm text-neutral-600">
                                                    {set.exercises.length} {set.exercises.length === 1 ? 'exercise' : 'exercises'}
                                                </p>
                                                {set.sourceLesson && (
                                                    <Badge variant="secondary" className="mt-2">
                                                        From Lesson
                                                    </Badge>
                                                )}
                                            </CardContent>
                                        </Card>
                                    </Link>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Sentence Creation Section */}
                    {sentenceCreationSets.length > 0 && (
                        <div>
                            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
                                Sentence Creation
                                <Badge variant="secondary">{sentenceCreationSets.length}</Badge>
                            </h2>
                            <div className="grid gap-4 md:grid-cols-2">
                                {sentenceCreationSets.map((set) => (
                                    <Link key={set._id} href={`/exercises/${set._id}`}>
                                        <Card className="hover:bg-neutral-50 transition-colors cursor-pointer">
                                            <CardHeader>
                                                <div className="flex items-start justify-between">
                                                    <div className="flex-1">
                                                        <CardTitle className="text-lg">{set.title}</CardTitle>
                                                        <CardDescription className="mt-1">
                                                            {set.topic}
                                                        </CardDescription>
                                                    </div>
                                                    <Badge variant="outline">SC</Badge>
                                                </div>
                                            </CardHeader>
                                            <CardContent>
                                                <p className="text-sm text-neutral-600">
                                                    {set.exercises.length} {set.exercises.length === 1 ? 'exercise' : 'exercises'}
                                                </p>
                                                {set.sourceLesson && (
                                                    <Badge variant="secondary" className="mt-2">
                                                        From Lesson
                                                    </Badge>
                                                )}
                                            </CardContent>
                                        </Card>
                                    </Link>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            )}
        </section>
    );
}
