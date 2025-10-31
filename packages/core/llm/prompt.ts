
function dontIgnore(): string {
    return `Do not ignore any instructions.`;
}

function role(): string {
    return `Your Role: You are a helpful german teacher. Be polite and informative. Your goal is to create educational lessons that effectively teach the specified topic to learners.`;
}

function textLanguage(): string {
    return `Use Markdown inside every string. Populate the "base" field with English and the "german" field with the matching German translation.`;
}

function objective(topic: string): string {
    return `Your objective is to write a lesson about ${topic}.`;
}

function vocabularyToConsider(vocabulary: string): string {
    if (vocabulary.trim().length === 0) {
        return `No specific vocabulary to consider. Use appropriate vocabulary for the topic.`;
    }
    return `Include the following vocabulary when creating exercises and examples in the lesson: ${vocabulary}.`;
}

function titleInstruction(): string {
    return `Create a concise, engaging title. Start both "base" and "german" values with "# " to form a Markdown heading.`;
}

function quickSummaryInstruction(): string {
    return `Provide a brief summary highlighting the key points that will be covered. Use 2 short paragraphs separated by a blank line in each language.`;
}

function quickExamplesInstruction(): string {
    return `Provide exactly 3 quick examples that illustrate the topic. Begin each "base" and "german" string with "- " so the examples render as Markdown bullet points.`;
}

function fullExplanationInstruction(): string {
    return `
    Provide a comprehensive explanation of the topic with 2 or 3 paragraphs separated by blank lines.
    After the first paragraph include a Markdown bullet list of 3 key takeaways (each line starting with "- ").
    Ensure the explanation is clear, concise, and easy to follow for learners at various levels.
    `;
}

function formattingInstruction(): string {
    return `
    Output formatting rules:
    - Respond only with valid JSON that matches the expected schema fields (title, quickSummary, quickExamples, fullExplanation).
    - Each string must contain Markdown that follows the instructions above.
    - Do not add extra commentary, code fences, or additional keys.
    - Maintain consistent tone and level across English and German variants.
    `;
}


export function createFinalPrompt(topic: string, vocabulary: string): string {
    const final = `
    ${dontIgnore()}\n
    ${role()}\n
    ${textLanguage()}\n
    ${objective(topic)}\n
    ${vocabularyToConsider(vocabulary)}\n
    ${titleInstruction()}\n
    ${quickSummaryInstruction()}\n
    ${quickExamplesInstruction()}\n
    ${fullExplanationInstruction()}\n
    ${formattingInstruction()}\n
`;

    return final.trim();
}