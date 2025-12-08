'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from '@/components/ui/dialog';
import { Info } from 'lucide-react';

interface MetadataResponse {
    operations?: Array<{
        operation: string;
        modelUsed: string;
        inputTokens: number;
        outputTokens: number;
        totalTokens: number;
        inputCost: number;
        outputCost: number;
        totalCost: number;
        timestamp: string;
        executionTimeMs: number;
    }>;
    totals?: {
        totalTokens: number;
        totalCost: number;
    };
}

interface LessonMetadataDialogProps {
    lessonId: string;
}

export function LessonMetadataDialog({ lessonId }: LessonMetadataDialogProps) {
    const [open, setOpen] = useState(false);
    const [metadata, setMetadata] = useState<MetadataResponse | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (open && !metadata) {
            fetchMetadata();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [open]);

    const fetchMetadata = async () => {
        setIsLoading(true);
        setError(null);

        try {
            const response = await fetch(`/api/lessons/${lessonId}/metadata`);

            if (!response.ok) {
                const payload = await response.json().catch(() => null);
                const message =
                    typeof payload?.error === 'string'
                        ? payload.error
                        : 'Failed to fetch metadata.';
                throw new Error(message);
            }

            const data = await response.json();
            setMetadata(data);
        } catch (err) {
            const message =
                err instanceof Error ? err.message : 'Something went wrong.';
            setError(message);
        } finally {
            setIsLoading(false);
        }
    };

    const formatCost = (cost: number) => {
        return `$${cost.toFixed(6)}`;
    };

    const formatDate = (dateString: string | null) => {
        if (!dateString) return 'N/A';
        return new Date(dateString).toLocaleString();
    };

    const formatOperation = (operation: string) => {
        const mapping: Record<string, string> = {
            lesson_creation: 'Lesson Creation',
            extra_section: 'Extra Section',
            chat: 'Chat with Nina',
            flashcard_generation: 'Flash Card Generation',
        };
        return mapping[operation] || operation;
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button size="icon" variant="secondary">
                    <Info></Info>
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[600px] max-h-[80vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Lesson Usage Metadata</DialogTitle>
                    <DialogDescription>
                        View token usage and costs for this lesson
                    </DialogDescription>
                </DialogHeader>

                {isLoading && (
                    <div className="flex items-center justify-center py-8">
                        <p className="text-sm text-neutral-600">Loading metadata...</p>
                    </div>
                )}

                {error && (
                    <div className="rounded-lg bg-error-bg p-4 border border-error-border">
                        <p className="text-sm text-error-text">{error}</p>
                    </div>
                )}

                {metadata && !isLoading && !error && (
                    <div className="space-y-6 py-4">
                        {/* All Operations */}
                        {metadata.operations && metadata.operations.length > 0 && (
                            <div className="space-y-3">
                                <h3 className="font-semibold text-sm border-b pb-2">
                                    Operations
                                </h3>
                                <div className="space-y-3">
                                    {metadata.operations.map((op, index) => (
                                        <div
                                            key={index}
                                            className="rounded-lg border border-neutral-200 p-4 space-y-3"
                                        >
                                            <div className="flex items-center justify-between">
                                                <p className="font-semibold text-sm">
                                                    {formatOperation(op.operation)}
                                                </p>
                                                <p className="text-xs text-neutral-600">
                                                    {formatDate(op.timestamp)}
                                                </p>
                                            </div>
                                            <div className="grid grid-cols-2 gap-3 text-xs">
                                                <div>
                                                    <p className="text-neutral-600">Model</p>
                                                    <p className="font-medium">
                                                        {op.modelUsed === 'gpt-5-nano'
                                                            ? 'GPT-5 Nano'
                                                            : 'GPT-4o Mini'}
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-neutral-600">Time</p>
                                                    <p className="font-medium">
                                                        {(op.executionTimeMs / 1000).toFixed(2)}s
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-neutral-600">Input Tokens</p>
                                                    <p className="font-medium">
                                                        {op.inputTokens.toLocaleString()}
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-neutral-600">Output Tokens</p>
                                                    <p className="font-medium">
                                                        {op.outputTokens.toLocaleString()}
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-neutral-600">Total Tokens</p>
                                                    <p className="font-medium">
                                                        {op.totalTokens.toLocaleString()}
                                                    </p>
                                                </div>
                                                <div>
                                                    <p className="text-neutral-600">Total Cost</p>
                                                    <p className="font-medium text-teal-600">
                                                        {formatCost(op.totalCost)}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Total Summary */}
                        {metadata.operations && metadata.operations.length > 0 && metadata.totals && (
                            <div className="rounded-lg bg-neutral-50 p-4 border border-neutral-200">
                                <h3 className="font-semibold text-sm mb-3">Total Usage</h3>
                                <div className="grid grid-cols-2 gap-3 text-sm">
                                    <div>
                                        <p className="text-neutral-600">Total Tokens</p>
                                        <p className="font-semibold text-lg">
                                            {metadata.totals.totalTokens.toLocaleString()}
                                        </p>
                                    </div>
                                    <div>
                                        <p className="text-neutral-600">Total Cost</p>
                                        <p className="font-semibold text-lg text-teal-600">
                                            {formatCost(metadata.totals.totalCost)}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}

                        {(!metadata.operations || metadata.operations.length === 0) && (
                            <div className="text-center py-8 text-neutral-500">
                                No usage data available for this lesson.
                            </div>
                        )}
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}
