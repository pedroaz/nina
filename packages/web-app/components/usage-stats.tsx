'use client';

import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

interface UsageSummary {
    totalInputTokens: number;
    totalOutputTokens: number;
    totalTokens: number;
    totalCost: number;
    totalInputCost: number;
    totalOutputCost: number;
    operationCount: number;
}

interface OperationBreakdown {
    _id: string;
    count: number;
    totalTokens: number;
    totalCost: number;
}

interface ModelBreakdown {
    _id: string;
    count: number;
    totalTokens: number;
    totalCost: number;
}

export function UsageStats() {
    const [summary, setSummary] = useState<UsageSummary | null>(null);
    const [operationBreakdown, setOperationBreakdown] = useState<OperationBreakdown[]>([]);
    const [modelBreakdown, setModelBreakdown] = useState<ModelBreakdown[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchUsage = async () => {
            try {
                const response = await fetch('/api/user/usage');
                if (response.ok) {
                    const data = await response.json();
                    setSummary(data.summary);
                    setOperationBreakdown(data.operationBreakdown);
                    setModelBreakdown(data.modelBreakdown);
                }
            } catch (error) {
                console.error('Failed to fetch usage data:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchUsage();
    }, []);

    if (loading) {
        return (
            <Card>
                <CardContent className="p-6">
                    <p className="text-center text-neutral-600">Loading usage data...</p>
                </CardContent>
            </Card>
        );
    }

    if (!summary) {
        return (
            <Card>
                <CardContent className="p-6">
                    <p className="text-center text-neutral-600">No usage data available.</p>
                </CardContent>
            </Card>
        );
    }

    return (
        <div className="space-y-6">
            <Card>
                <CardHeader>
                    <CardTitle>Usage Summary</CardTitle>
                    <CardDescription>Your total AI usage and costs</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-sm">Total Operations</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-3xl font-bold">{summary.operationCount.toLocaleString()}</p>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-sm">Total Tokens</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-3xl font-bold">{summary.totalTokens.toLocaleString()}</p>
                                <p className="text-xs text-neutral-600 mt-2">
                                    {summary.totalInputTokens.toLocaleString()} in / {summary.totalOutputTokens.toLocaleString()} out
                                </p>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-sm">Total Cost</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-3xl font-bold">${(summary.totalCost ?? 0).toFixed(4)}</p>
                                <p className="text-xs text-neutral-600 mt-2">
                                    ${(summary.totalInputCost ?? 0).toFixed(4)} in / ${(summary.totalOutputCost ?? 0).toFixed(4)} out
                                </p>
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader>
                                <CardTitle className="text-sm">Avg Cost/Operation</CardTitle>
                            </CardHeader>
                            <CardContent>
                                <p className="text-3xl font-bold">
                                    ${(summary.operationCount > 0 ? summary.totalCost / summary.operationCount : 0).toFixed(4)}
                                </p>
                            </CardContent>
                        </Card>
                    </div>
                </CardContent>
            </Card>

            <div className="grid gap-6 md:grid-cols-2">
                <Card>
                    <CardHeader>
                        <CardTitle>By Operation Type</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            {operationBreakdown.map((op) => (
                                <div key={op._id} className="flex items-center justify-between p-3 border border-neutral-200 rounded">
                                    <div>
                                        <p className="font-medium text-sm">{op._id.replace(/_/g, ' ')}</p>
                                        <p className="text-xs text-neutral-600">
                                            {op.count} operations • {op.totalTokens.toLocaleString()} tokens
                                        </p>
                                    </div>
                                    <p className="font-semibold">${(op.totalCost ?? 0).toFixed(4)}</p>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle>By Model</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-3">
                            {modelBreakdown.map((model) => (
                                <div key={model._id} className="flex items-center justify-between p-3 border border-neutral-200 rounded">
                                    <div>
                                        <p className="font-medium text-sm">{model._id}</p>
                                        <p className="text-xs text-neutral-600">
                                            {model.count} operations • {model.totalTokens.toLocaleString()} tokens
                                        </p>
                                    </div>
                                    <p className="font-semibold">${(model.totalCost ?? 0).toFixed(4)}</p>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}
