'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardAction,
    CardContent,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';

type LanguageKey = 'base' | 'german';

export type DualLanguageContent = {
    base?: string | null;
    german?: string | null;
};

type DualLanguageTextCardProps = {
    heading: string;
    content: DualLanguageContent | DualLanguageContent[] | null | undefined;
    emptyMessage?: string;
};

const buttonLabel: Record<LanguageKey, string> = {
    base: 'Show German',
    german: 'Show Base',
};

const languageLabel: Record<LanguageKey, string> = {
    base: 'Base',
    german: 'German',
};

function getEntries(
    content: DualLanguageContent | DualLanguageContent[] | null | undefined,
): DualLanguageContent[] {
    if (!content) {
        return [];
    }

    return Array.isArray(content) ? content : [content];
}

function hasContent(entry: DualLanguageContent): boolean {
    return ['base', 'german'].some((key) => {
        const value = entry?.[key as LanguageKey];
        return typeof value === 'string' && value.trim().length > 0;
    });
}

function getEntryText(entry: DualLanguageContent, language: LanguageKey): string {
    const value = entry?.[language];
    if (typeof value === 'string' && value.trim().length > 0) {
        return value.trim();
    }

    return `No ${languageLabel[language]} content provided.`;
}

export function DualLanguageTextCard({
    heading,
    content,
    emptyMessage = 'No content available.',
}: DualLanguageTextCardProps) {
    const [activeLanguage, setActiveLanguage] = useState<LanguageKey>('base');
    const entries = getEntries(content);
    const hasAnyContent = entries.some(hasContent);

    const handleToggle = () => {
        setActiveLanguage((prev) => (prev === 'base' ? 'german' : 'base'));
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle className="text-lg font-semibold">{heading}</CardTitle>
                <CardAction>
                    <div className="flex items-center gap-2">
                        {/* <span className="text-xs font-medium uppercase text-muted-foreground">
                            {languageLabel[activeLanguage]}
                        </span> */}
                        <Button size="sm" variant="outline" onClick={handleToggle}>
                            {buttonLabel[activeLanguage]}
                        </Button>
                    </div>
                </CardAction>
            </CardHeader>
            <CardContent>
                {!hasAnyContent ? (
                    <p className="text-sm text-muted-foreground">{emptyMessage}</p>
                ) : entries.length === 1 ? (
                    <p className="whitespace-pre-wrap text-sm leading-6 text-slate-700">
                        {getEntryText(entries[0], activeLanguage)}
                    </p>
                ) : (
                    <ol className="list-decimal space-y-2 pl-5">
                        {entries.map((entry, index) => (
                            <li
                                key={`${heading}-${index}`}
                                className="whitespace-pre-wrap text-sm leading-6 text-slate-700"
                            >
                                {getEntryText(entry, activeLanguage)}
                            </li>
                        ))}
                    </ol>
                )}
            </CardContent>
        </Card>
    );
}
