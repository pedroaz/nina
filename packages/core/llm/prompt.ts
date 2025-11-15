
function dontIgnore(): string {
    return `Do not ignore any instructions.`;
}

function role(targetLanguage: string): string {
    return `Your Role: You are a helpful ${targetLanguage} teacher. Be polite and informative. Your goal is to create educational lessons that effectively teach the specified topic to learners.`;
}

function textLanguage(baseLanguage: string, targetLanguage: string): string {
    return `Use Markdown inside every string. Populate the "base" field with ${baseLanguage} and the "target" field with the matching ${targetLanguage} translation.`;
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
    return `Create a concise, engaging title. Start both "base" and "target" values with "# " to form a Markdown heading.`;
}

function quickSummaryInstruction(): string {
    return `Provide a brief summary highlighting the key points that will be covered. Use 2 short paragraphs separated by a blank line in each language.`;
}

function quickExamplesInstruction(): string {
    return `Provide exactly 3 quick examples that illustrate the topic.
    IMPORTANT: Each example must be a SEPARATE object with its own "base" and "target" fields.
    - The "base" field contains ONLY the example in the base language
    - The "target" field contains ONLY the translation in the target language
    - Begin each string with "- " so the examples render as Markdown bullet points
    - Do NOT put both languages in the same field`;
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
    - Each field (title, quickSummary, fullExplanation) must be an object with BOTH "base" and "target" properties.
    - quickExamples must be an array of objects, where each object has BOTH "base" and "target" properties.
    - Each string must contain Markdown that follows the instructions above.
    - Do not add extra commentary, code fences, or additional keys outside of these fields.
    - Do not create a separate "target" field at the root level - the target language content belongs inside each field's "target" property.
    - Maintain consistent tone and level across both language variants.

    Example structure:
    {
      "title": {
        "base": "# Title in base language",
        "target": "# Title in target language"
      },
      "quickSummary": {
        "base": "Summary in base language",
        "target": "Summary in target language"
      },
      "quickExamples": [
        {
          "base": "- First example in base language ONLY",
          "target": "- First example in target language ONLY"
        },
        {
          "base": "- Second example in base language ONLY",
          "target": "- Second example in target language ONLY"
        },
        {
          "base": "- Third example in base language ONLY",
          "target": "- Third example in target language ONLY"
        }
      ],
      "fullExplanation": {
        "base": "Full explanation in base language",
        "target": "Full explanation in target language"
      }
    }
    `;
}


export function createFinalPrompt(
    topic: string,
    vocabulary: string,
    baseLanguage: string,
    targetLanguage: string
): string {
    const final = `
    ${dontIgnore()}\n
    ${role(targetLanguage)}\n
    ${textLanguage(baseLanguage, targetLanguage)}\n
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