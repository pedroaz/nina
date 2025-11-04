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

const markdownPreviewStyle = {
    backgroundColor: 'transparent',
    padding: 0,
    color: 'inherit',
    fontFamily: 'inherit',
    '--color-canvas-default': 'transparent',
    '--color-canvas-subtle': 'transparent',
} as CSSProperties;

const translationPreviewStyle = {
    backgroundColor: 'transparent',
    padding: 0,
    color: '#c2410c', // orange-700
    fontFamily: 'inherit',
    '--color-canvas-default': 'transparent',
    '--color-canvas-subtle': 'transparent',
} as CSSProperties;

const markdownPreviewClassName =
    'text-sm leading-6 text-slate-700 whitespace-pre-wrap [&>*]:m-0 [&>*:not(:last-child)]:mb-2';

const translationPreviewClassName =
    'text-xs leading-5 whitespace-pre-wrap [&>*]:m-0 [&>*:not(:last-child)]:mb-2 mt-2';

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

function splitIntoParagraphs(text: string): string[] {
    // Split by double newlines and filter out empty paragraphs
    return text
        .split('\n\n')
        .map((p) => p.trim())
        .filter((p) => p.length > 0);
}

function canSplitIntoParagraphs(entry: DualLanguageContent): boolean {
    const germanText = entry?.german;
    const baseText = entry?.base;

    if (
        typeof germanText !== 'string' ||
        germanText.trim().length === 0 ||
        typeof baseText !== 'string' ||
        baseText.trim().length === 0
    ) {
        return false;
    }

    const germanParagraphs = splitIntoParagraphs(germanText);
    const baseParagraphs = splitIntoParagraphs(baseText);

    return germanParagraphs.length === baseParagraphs.length && germanParagraphs.length > 0;
}

function getEntryText(entry: DualLanguageContent, language: LanguageKey): string {
    const value = entry?.[language];
    if (typeof value === 'string' && value.trim().length > 0) {
        return value.trim();
    }

    const languageNames: Record<LanguageKey, string> = {
        base: 'English',
        german: 'German',
    };

    return `No ${languageNames[language]} content provided.`;
}

function renderEntryContent(entry: DualLanguageContent, showTranslation: boolean) {
    const canSplit = canSplitIntoParagraphs(entry);

    if (canSplit) {
        // Split into paragraphs and show German with optional translation below
        const germanText = entry.german?.trim() ?? '';
        const baseText = entry.base?.trim() ?? '';
        const germanParagraphs = splitIntoParagraphs(germanText);
        const baseParagraphs = splitIntoParagraphs(baseText);

        return (
            <div>
                {germanParagraphs.map((germanPara, index) => (
                    <div key={index} className="mb-4 last:mb-0">
                        <MarkdownPreview
                            className={markdownPreviewClassName}
                            source={germanPara}
                            style={markdownPreviewStyle}
                            wrapperElement={{ 'data-color-mode': 'light' }}
                        />
                        {showTranslation && (
                            <MarkdownPreview
                                className={translationPreviewClassName}
                                source={baseParagraphs[index]}
                                style={translationPreviewStyle}
                                wrapperElement={{ 'data-color-mode': 'light' }}
                            />
                        )}
                    </div>
                ))}
            </div>
        );
    } else {
        // Fallback: show German by default, toggle to show base if needed
        console.warn(
            'Paragraph counts do not match for entry. Falling back to toggle behavior.',
        );
        const displayLanguage: LanguageKey = showTranslation ? 'base' : 'german';
        return (
            <MarkdownPreview
                className={markdownPreviewClassName}
                source={getEntryText(entry, displayLanguage)}
                style={markdownPreviewStyle}
                wrapperElement={{ 'data-color-mode': 'light' }}
            />
        );
    }
}

export function DualLanguageTextCard({
    heading,
    content,
    emptyMessage = 'No content available.',
}: DualLanguageTextCardProps) {
    const [showTranslation, setShowTranslation] = useState<boolean>(false);
    const [highlightedText, setHighlightedText] = useState<string>('');
    const entries = getEntries(content);
    const hasAnyContent = entries.some(hasContent);

    const handleToggle = () => {
        setShowTranslation((prev) => !prev);
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
                        <Button size="sm" variant="outline" onClick={handleToggle}>
                            {showTranslation ? 'Translate' : 'Translate'}
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
                            ) : (
                                <div>
                                    {entries.map((entry, index) => (
                                        <div
                                            key={`${heading}-${index}`}
                                        >
                                            {renderEntryContent(entry, showTranslation)}
                                        </div>
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
