import { Suspense } from "react";
import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import { authOptions } from "@/app/api/auth/[...nextauth]/route";
import { getUserByEmail } from "@core/index";
import { UsageStats } from "@/components/usage-stats";
import { DashboardStats } from "@/components/dashboard-stats";
import { PentagonSpinner } from "@/components/pentagon-spinner";

export default function Home() {
  return (
    <div className="container mx-auto px-4 py-10">
      <h1 className="text-3xl font-bold mb-2">Dashboard</h1>
      <Suspense fallback={<PentagonSpinner />}>
        <DashboardContent />
      </Suspense>
    </div>
  );
}

async function DashboardContent() {
  const session = await getServerSession(authOptions);

  if (!session?.user?.email) {
    redirect('/api/auth/signin');
  }

  const user = await getUserByEmail(session.user.email);

  if (!user) {
    redirect('/api/auth/signin');
  }

  return (
    <>
      <div className="mb-8">
        <p className="text-neutral-600">
          Welcome back, {user.name}! Here's your learning progress.
        </p>
      </div>

      <div className="space-y-8">
        <DashboardStats userId={user._id.toString()} />
        <UsageStats />
      </div>
    </>
  );
}
