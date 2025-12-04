
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

    CRITICAL: fullExplanation MUST be an object with BOTH "base" and "target" properties, just like title and quickSummary.
    `;
}

function formattingInstruction(): string {
  return `
    CRITICAL OUTPUT FORMATTING RULES - READ CAREFULLY:

    1. STRUCTURE: The JSON must contain EXACTLY these root-level fields: _id, __v, title, quickSummary, quickExamples, fullExplanation
       - Set _id to "1" and __v to 0

    2. OBJECT FIELDS: title, quickSummary, and fullExplanation are ALL objects with the SAME structure:
       {
         "base": "content in base language",
         "target": "content in target language"
       }

    3. ARRAY FIELD: quickExamples is an array of 3 objects, each with:
       {
         "base": "- example in base language ONLY",
         "target": "- example in target language ONLY"
       }

    4. FORBIDDEN: Do NOT create:
       - A separate "target" field at the root level
       - Any field that is just an object with only "base" or only "target"
       - Any extra fields beyond the required ones

    5. REQUIRED: Every object field (title, quickSummary, fullExplanation) MUST have BOTH "base" AND "target" properties

    CORRECT Example:
    {
      "_id": "1",
      "__v": 0,
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
        "base": "Full explanation in base language with paragraphs and bullet points",
        "target": "Full explanation in target language with paragraphs and bullet points"
      }
    }

    INCORRECT Example (DO NOT DO THIS):
    {
      "fullExplanation": {
        "base": "..."
      },
      "target": {  ← WRONG! This should not exist at root level
        "base": "..."
      }
    }
    `;
}



function focusInstruction(focus?: 'vocabulary' | 'grammar'): string {
  if (focus === 'grammar') {
    return `
    FOCUS INSTRUCTION: GRAMMAR
    - The primary goal of this lesson is to teach GRAMMAR rules and structures.
    - The "fullExplanation" should explain the grammar concepts in depth, with clear rules and exceptions.
    - The "quickExamples" should specifically demonstrate the grammar points being taught.
    - Vocabulary used should be simple and supportive of the grammar lesson, unless specific vocabulary was requested.
        `;
  } else if (focus === 'vocabulary') {
    return `
    FOCUS INSTRUCTION: VOCABULARY
    - The primary goal of this lesson is to teach new VOCABULARY.
    - The "fullExplanation" should focus on usage, nuance, and context of the vocabulary words.
    - The "quickExamples" should show the vocabulary words in natural sentences.
    - Grammar used should be appropriate for the learner but secondary to the vocabulary acquisition.
        `;
  }
  return '';
}

export function createFinalPrompt(
  topic: string,
  vocabulary: string,
  baseLanguage: string,
  targetLanguage: string,
  focus?: 'vocabulary' | 'grammar'
): string {
  const final = `
    ${dontIgnore()}\n
    ${role(targetLanguage)}\n
    ${textLanguage(baseLanguage, targetLanguage)}\n
    ${objective(topic)}\n
    ${vocabularyToConsider(vocabulary)}\n
    ${focusInstruction(focus)}\n
    ${titleInstruction()}\n
    ${quickSummaryInstruction()}\n
    ${quickExamplesInstruction()}\n
    ${fullExplanationInstruction()}\n
    ${formattingInstruction()}\n
`;

  return final.trim();
}