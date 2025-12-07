'use client';

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";

interface CollectionStat {
    collection: string;
    count: number;
}

export function AdminDatabasePanel() {
    const [isDialogOpen, setIsDialogOpen] = useState(false);
    const [stats, setStats] = useState<CollectionStat[] | null>(null);
    const [isLoadingStats, setIsLoadingStats] = useState(false);
    const [isClearing, setIsClearing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const handleOpenDialog = async () => {
        setIsDialogOpen(true);
        setIsLoadingStats(true);
        setError(null);
        setSuccessMessage(null);

        try {
            const response = await fetch("/api/admin/clear-database");
            if (!response.ok) {
                throw new Error("Failed to load database statistics");
            }
            const data = await response.json();
            setStats(data.stats);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load stats");
        } finally {
            setIsLoadingStats(false);
        }
    };

    const handleClearDatabase = async () => {
        setIsClearing(true);
        setError(null);

        try {
            const response = await fetch("/api/admin/clear-database", {
                method: "DELETE",
            });

            if (!response.ok) {
                throw new Error("Failed to clear database");
            }

            const result = await response.json();

            setSuccessMessage(
                `Successfully cleared ${result.totalDeleted} records from ${result.deletedCollections.length} collections.`
            );

            // Close dialog after brief delay
            setTimeout(() => {
                setIsDialogOpen(false);
                setStats(null);
            }, 2000);

        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to clear database");
        } finally {
            setIsClearing(false);
        }
    };

    const totalRecords = stats?.reduce((sum, stat) => sum + stat.count, 0) ?? 0;

    return (
        <>
            <Card>
                <CardHeader>
                    <CardTitle>Database Management</CardTitle>
                    <CardDescription>
                        Danger zone: Irreversible database operations
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="space-y-4">
                        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                            <h3 className="text-sm font-semibold text-red-900 mb-2">
                                Clear All Database Tables
                            </h3>
                            <p className="text-sm text-red-700 mb-3">
                                This will permanently delete all data from all database collections.
                                This action cannot be undone.
                            </p>
                            <Button
                                variant="destructive"
                                onClick={handleOpenDialog}
                                disabled={isClearing}
                            >
                                Clear Database
                            </Button>
                        </div>

                        {successMessage && (
                            <div className="rounded-lg border border-green-200 bg-green-50 p-4">
                                <p className="text-sm text-green-900">{successMessage}</p>
                            </div>
                        )}
                    </div>
                </CardContent>
            </Card>

            <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                <DialogContent className="sm:max-w-[500px]">
                    <DialogHeader>
                        <DialogTitle>Confirm Database Clear</DialogTitle>
                        <DialogDescription>
                            This action will permanently delete all data. Review the counts below.
                        </DialogDescription>
                    </DialogHeader>

                    <div className="py-4">
                        {isLoadingStats ? (
                            <p className="text-sm text-neutral-500">Loading statistics...</p>
                        ) : stats ? (
                            <div className="space-y-3">
                                <div className="rounded-lg border border-neutral-200 bg-neutral-50 p-3">
                                    <p className="text-sm font-semibold mb-2">
                                        Total records to delete: {totalRecords}
                                    </p>
                                    <div className="space-y-1">
                                        {stats.map((stat) => (
                                            <div
                                                key={stat.collection}
                                                className="flex justify-between text-xs"
                                            >
                                                <span className="text-neutral-600">
                                                    {stat.collection}
                                                </span>
                                                <span className="font-mono text-neutral-900">
                                                    {stat.count}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {error && (
                                    <div className="rounded-lg border border-red-200 bg-red-50 p-3">
                                        <p className="text-sm text-red-900">{error}</p>
                                    </div>
                                )}

                                {!error && (
                                    <div className="rounded-lg border border-orange-200 bg-orange-50 p-3">
                                        <p className="text-xs text-orange-900">
                                            WARNING: This operation cannot be undone. All user data,
                                            lessons, exercises, and progress will be permanently lost.
                                        </p>
                                    </div>
                                )}
                            </div>
                        ) : null}
                    </div>

                    <DialogFooter>
                        <Button
                            variant="outline"
                            onClick={() => setIsDialogOpen(false)}
                            disabled={isClearing}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="destructive"
                            onClick={handleClearDatabase}
                            disabled={isClearing || isLoadingStats || !!error}
                        >
                            {isClearing ? "Clearing..." : "Confirm & Clear"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
