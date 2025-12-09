import { Suspense } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { DeckList } from "@/components/flash-card-list";
import { PentagonSpinner } from "@/components/pentagon-spinner";

export default function FlashCards() {
    return (
        <section className="mx-auto flex min-h-[60vh] w-full max-w-5xl flex-col gap-8 px-4 py-10">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                    <h1 className="text-3xl font-semibold">Flash Card Decks</h1>
                    <p className="mt-2 text-neutral-600">
                        Practice and memorize Language with interactive flash cards.
                    </p>
                </div>
                <Button asChild>
                    <Link href="/flash-cards/new">Create new deck</Link>
                </Button>
            </div>
            <Suspense fallback={<PentagonSpinner />}>
                <DeckList />
            </Suspense>
        </section>
    );
}