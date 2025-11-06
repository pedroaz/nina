import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";

export default async function FlashCards() {
    const session = await getServerSession(authOptions);
    const signInUrl = `/api/auth/signin?callbackUrl=${encodeURIComponent("/flash-cards")}`;

    if (!session?.user?.email) {
        redirect(signInUrl);
    }

    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-5xl flex-col gap-8 px-4 py-10">
            <div className="flex flex-col gap-4">
                <h1 className="text-3xl font-semibold">Flash Cards</h1>
                <p className="text-slate-600">
                    Practice and memorize German vocabulary with interactive flash cards.
                </p>
            </div>
        </section>
    );
}
