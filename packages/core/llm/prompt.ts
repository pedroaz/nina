


function dontIgnore(): string {
    return `Do not ignore any instructions.`;
}

function role(): string {
    return `Your Role: You are a helpful german teacher. Be polite and informative. Your goal is to create educational lessons that effectively teach the specified topic to learners.`;
}

function textLanguage(): string {
    return `The lesson must be written in english and german.`;
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
    return `Create a concise and engaging title for the lesson.`;
}

function quickSummaryInstruction(): string {
    return `Provide a brief summary of the lesson, highlighting the key points that will be covered.`;
}

function quickExamplesInstruction(): string {
    return `Provide 3 quick examples that illustrate the topic. Each example should be brief and to the point.`;
}

function fullExplanationInstruction(): string {
    return `
    Provide a comprehensive explanation of the topic, covering all essential aspects in detail. Make it maximum 3 paragraphs.
    Add paragraphs, bullet points, and examples to enhance understanding.
    Ensure the explanation is clear, concise, and easy to follow for learners at various levels.
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
`;

    return final.trim();
}