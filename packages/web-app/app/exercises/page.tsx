import Link from "next/link";
import { getExerciseSetsByUserIdQuery, ExerciseSet } from "@core/index";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { getAuthenticatedUser } from "@/lib/get-authenticated-user";
import { ExerciseSection } from "@/components/exercises/exercise-section";

const EXERCISE_TYPES: { type: ExerciseSet['type']; label: string }[] = [
    { type: 'multiple_choice', label: 'Multiple Choice' },
    { type: 'sentence_creation', label: 'Sentence Creation' },
];

export default async function ExercisesPage() {
    const user = await getAuthenticatedUser("/exercises");
    const exerciseSets = await getExerciseSetsByUserIdQuery(user._id);

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
                    {EXERCISE_TYPES.map(({ type, label }) => (
                        <ExerciseSection
                            key={type}
                            title={label}
                            exerciseSets={exerciseSets.filter((set) => set.type === type)}
                        />
                    ))}
                </div>
            )}
        </section>
    );
}
