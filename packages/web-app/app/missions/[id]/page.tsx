import { notFound } from "next/navigation";
import { getMissionById } from "@core/index";
import { getAuthenticatedUser } from "@/lib/get-authenticated-user";
import { MissionChat } from "@/components/mission-chat";

type MissionPageProps = {
    params: Promise<{
        id: string;
    }>;
};

export default async function MissionPage({ params }: MissionPageProps) {
    const { id } = await params;
    await getAuthenticatedUser(`/missions/${id}`);

    const mission = await getMissionById(id);

    if (!mission) {
        notFound();
    }

    // Convert MongoDB document to plain object for client component
    const plainMission = JSON.parse(JSON.stringify(mission));

    return <MissionChat mission={plainMission} />;
}
