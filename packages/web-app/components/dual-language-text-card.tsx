'use client';

import { useState } from 'react';
import type { CSSProperties } from 'react';
import MarkdownPreview from '@uiw/react-markdown-preview';
import { Button } from '@/components/ui/button';
import {
    Card,
    CardAction,
    CardContent,
    CardHeader,
    CardTitle,
} from '@/components/ui/card';
import {
    ContextMenu,
    ContextMenuContent,
    ContextMenuItem,
    ContextMenuTrigger,
} from '@/components/ui/context-menu';

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

const markdownPreviewStyle = {
    backgroundColor: 'transparent',
    padding: 0,
    color: 'inherit',
    fontFamily: 'inherit',
    '--color-canvas-default': 'transparent',
    '--color-canvas-subtle': 'transparent',
} as CSSProperties;

const markdownPreviewClassName =
    'text-sm leading-6 text-slate-700 whitespace-pre-wrap [&>*]:m-0 [&>*:not(:last-child)]:mb-2';

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
    const [highlightedText, setHighlightedText] = useState<string>('');
    const entries = getEntries(content);
    const hasAnyContent = entries.some(hasContent);

    const handleToggle = () => {
        setActiveLanguage((prev) => (prev === 'base' ? 'german' : 'base'));
    };

    const handleContextMenu = () => {
        // Capture the highlighted text right before the custom menu opens.
        const text = window.getSelection()?.toString().trim() ?? '';
        setHighlightedText(text);
    };

    const handleTranslate = () => {
        console.log('Translate sentence:', highlightedText);
    };

    const handleAddToFlashcard = () => {
        console.log('Add to flash card:', highlightedText);
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
                <ContextMenu>
                    <ContextMenuTrigger asChild>
                        <div onContextMenu={handleContextMenu}>
                            {!hasAnyContent ? (
                                <p className="text-sm text-muted-foreground">
                                    {emptyMessage}
                                </p>
                            ) : entries.length === 1 ? (
                                <MarkdownPreview
                                    className={markdownPreviewClassName}
                                    source={getEntryText(entries[0], activeLanguage)}
                                    style={markdownPreviewStyle}
                                    wrapperElement={{ 'data-color-mode': 'light' }}
                                />
                            ) : (
                                <div>
                                    {entries.map((entry, index) => (
                                        <MarkdownPreview
                                            key={`${heading}-${index}`}
                                            className={markdownPreviewClassName}
                                            source={getEntryText(entry, activeLanguage)}
                                            style={markdownPreviewStyle}
                                            wrapperElement={{ 'data-color-mode': 'light' }}
                                        />
                                    ))}
                                </div>
                            )}
                        </div>
                    </ContextMenuTrigger>
                    <ContextMenuContent>
                        <ContextMenuItem onSelect={handleTranslate} disabled={!highlightedText}>
                            Translate sentence
                        </ContextMenuItem>
                        <ContextMenuItem
                            onSelect={handleAddToFlashcard}
                            disabled={!highlightedText}
                        >
                            Add to flash card
                        </ContextMenuItem>
                    </ContextMenuContent>
                </ContextMenu>
            </CardContent>
        </Card>
    );
}
