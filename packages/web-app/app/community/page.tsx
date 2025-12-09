import { Suspense } from "react";
import { PentagonSpinner } from "@/components/pentagon-spinner";
import { getAuthenticatedSession } from "@/lib/get-authenticated-user";

export default function Community() {
    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-5xl flex-col gap-8 px-4 py-10">
            <div className="flex flex-col gap-4">
                <h1 className="text-3xl font-semibold">Community</h1>
                <p className="text-neutral-600">
                    Connect with other Language learners, share experiences, and grow together.
                </p>
            </div>
            <Suspense fallback={<PentagonSpinner />}>
                <AuthCheck />
            </Suspense>
        </section>
    );
}

async function AuthCheck() {
    await getAuthenticatedSession("/community");
    return null;
}
