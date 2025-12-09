import { getAuthenticatedSession } from "@/lib/get-authenticated-user";

export default async function LearningPath() {
    await getAuthenticatedSession("/learning-path");

    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-5xl flex-col gap-8 px-4 py-10">
            <div className="flex flex-col gap-4">
                <h1 className="text-3xl font-semibold">Learning Path</h1>
                <p className="text-neutral-600">
                    Track your progress and follow a personalized path to fluency.
                </p>
            </div>
        </section>
    );
}
