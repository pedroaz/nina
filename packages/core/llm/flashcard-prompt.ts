import { StudentLevel } from "../entities/student";

function role(targetLanguage: string): string {
  return `Your Role: You are a helpful language teacher creating flash cards for language learners. Be concise and educational. Your goal is to create effective flash cards that help learners practice and memorize ${targetLanguage} vocabulary and phrases.`;
}

function cardFormat(baseLanguage: string, targetLanguage: string): string {
  return `Flash Card Format: Each card should have:
- "base": A ${baseLanguage} sentence or phrase (full sentence, not just a single word)
- "target": The accurate ${targetLanguage} translation of that sentence

Make sure the sentences are practical, natural, and useful for everyday communication.`;
}

function levelGuidance(studentLevel: StudentLevel): string {
  const levelGuides: Record<StudentLevel, string> = {
    'A1': 'Create simple, everyday sentences using basic vocabulary and present tense. Focus on greetings, numbers, family, food, and common daily activities.',
    'A2': 'Create sentences about familiar topics using simple grammar structures. Include past tense and basic compound sentences about personal experiences.',
    'B1': 'Create sentences about concrete and abstract topics using intermediate grammar. Include different tenses, modal verbs, and more complex sentence structures.',
    'B2': 'Create detailed sentences on a wide range of topics. Use complex grammar structures, idiomatic expressions, and nuanced vocabulary.',
    'C1': 'Create sophisticated sentences with advanced vocabulary and complex grammatical structures. Include idiomatic expressions and cultural nuances.',
    'C2': 'Create native-level sentences with mastery of subtle meanings, colloquialisms, and cultural context. Use the full range of German linguistic complexity.',
  };

  return `Student Level: ${studentLevel}\n${levelGuides[studentLevel]}`;
}

export function createFlashCardFromPromptInstructions(
  topic: string,
  cardCount: number,
  studentLevel: StudentLevel,
  baseLanguage: string,
  targetLanguage: string
): string {
  return `
${role(targetLanguage)}

${cardFormat(baseLanguage, targetLanguage)}

${levelGuidance(studentLevel)}

Your Task: Create ${cardCount} flash cards about "${topic}".

Requirements:
1. Generate a suitable deck title for this topic (will be "title" field)
2. Create exactly ${cardCount} flash cards (will be "cards" array)
3. Each card must be a complete, natural sentence (not just vocabulary words)
4. Cards should cover different aspects of the topic
5. Ensure variety - use different sentence structures and contexts
6. Match the student's level (${studentLevel}) in complexity and vocabulary
7. Both ${baseLanguage} and ${targetLanguage} sentences should sound natural to native speakers

Output Format:
Return a JSON object with:
- "title": A short, descriptive deck title (string)
- "cards": An array of flash card objects, each with "base" (${baseLanguage}) and "target" (${targetLanguage} translation)

Example structure:
{
  "title": "${targetLanguage} Greetings",
  "cards": [
    { "base": "Good morning, how are you today?", "target": "Guten Morgen, wie geht es dir heute?" },
    ...
  ]
}
`.trim();
}

export function createFlashCardFromLessonInstructions(
  lessonTopic: string,
  lessonTitle: string,
  lessonSummary: string,
  lessonExplanation: string,
  cardCount: number,
  studentLevel: StudentLevel,
  baseLanguage: string,
  targetLanguage: string
): string {
  return `
${role(targetLanguage)}

${cardFormat(baseLanguage, targetLanguage)}

${levelGuidance(studentLevel)}

Your Task: Create ${cardCount} flash cards based on the following ${targetLanguage} lesson.

Lesson Information:
Topic: ${lessonTopic}
Title: ${lessonTitle}
Summary: ${lessonSummary}
Content: ${lessonExplanation}

Requirements:
1. Extract key concepts, phrases, and examples from the lesson
2. Create exactly ${cardCount} flash cards (will be "cards" array)
3. Each card must be a complete, natural sentence (not just vocabulary words)
4. Cards should reinforce the main concepts taught in the lesson
5. Include practical examples that demonstrate the lesson's grammar or vocabulary
6. Match the student's level (${studentLevel}) in complexity
7. Both ${baseLanguage} and ${targetLanguage} sentences should sound natural

Output Format:
Return a JSON object with:
- "cards": An array of flash card objects, each with "base" (${baseLanguage}) and "target" (${targetLanguage} translation)

Example structure:
{
  "cards": [
    { "base": "I am learning ${targetLanguage} at school.", "target": "Ich lerne Deutsch in der Schule." },
    ...
  ]
}
`.trim();
}
