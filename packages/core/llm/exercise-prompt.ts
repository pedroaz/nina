import { StudentLevel } from "../entities/student";

function role(targetLanguage: string): string {
  return `Your Role: You are a helpful language teacher creating exercises for language learners. Be educational and encouraging. Your goal is to create effective exercises that help learners practice and master ${targetLanguage} through active engagement.`;
}

function levelGuidance(studentLevel: StudentLevel): string {
  const levelGuides: Record<StudentLevel, string> = {
    'A1': 'Create simple exercises using basic vocabulary and present tense. Focus on greetings, numbers, family, food, and common daily activities.',
    'A2': 'Create exercises about familiar topics using simple grammar structures. Include past tense and basic compound sentences about personal experiences.',
    'B1': 'Create exercises about concrete and abstract topics using intermediate grammar. Include different tenses, modal verbs, and more complex sentence structures.',
    'B2': 'Create detailed exercises on a wide range of topics. Use complex grammar structures, idiomatic expressions, and nuanced vocabulary.',
    'C1': 'Create sophisticated exercises with advanced vocabulary and complex grammatical structures. Include idiomatic expressions and cultural nuances.',
    'C2': 'Create native-level exercises with mastery of subtle meanings, colloquialisms, and cultural context. Use the full range of linguistic complexity.',
  };

  return `Student Level: ${studentLevel}\n${levelGuides[studentLevel]}`;
}

// MULTIPLE CHOICE EXERCISES

function multipleChoiceFormat(baseLanguage: string, targetLanguage: string): string {
  return `Multiple Choice Exercise Format: Each exercise should have:
- "question": A question object with "base" (${baseLanguage}) and "target" (${targetLanguage}) - the question to answer
- "options": An array of 4 option objects, each with "base" (${baseLanguage}) and "target" (${targetLanguage})
- "correctOptionIndex": A number (0-3) indicating which option is correct

All questions and options should be in ${targetLanguage} in the "target" field, with ${baseLanguage} translations in the "base" field to help learners.
Make sure options are plausible but only one is clearly correct. Options should test real understanding, not trick questions.`;
}

export function createMultipleChoiceFromPromptInstructions(
  topic: string,
  exerciseCount: number,
  studentLevel: StudentLevel,
  baseLanguage: string,
  targetLanguage: string
): string {
  return `
${role(targetLanguage)}

${multipleChoiceFormat(baseLanguage, targetLanguage)}

${levelGuidance(studentLevel)}

Your Task: Create ${exerciseCount} multiple choice exercises about "${topic}".

Requirements:
1. Generate a suitable title for this exercise set (will be "title" field)
2. Create exactly ${exerciseCount} exercises (will be "exercises" array)
3. Each question should test practical knowledge of ${targetLanguage}
4. All 4 options should be plausible, but only one correct
5. Questions should cover different aspects of the topic
6. Match the student's level (${studentLevel}) in complexity and vocabulary
7. Both ${baseLanguage} and ${targetLanguage} should sound natural

Output Format:
Return a JSON object with:
- "title": A short, descriptive title (string)
- "exercises": An array of exercise objects

Example structure:
{
  "title": "${targetLanguage} ${topic} Practice",
  "exercises": [
    {
      "question": {
        "base": "What is the correct way to say 'hello' formally?",
        "target": "Was ist der richtige Weg, um formell 'Hallo' zu sagen?"
      },
      "options": [
        { "base": "Hi", "target": "Hi" },
        { "base": "Good day", "target": "Guten Tag" },
        { "base": "Hey", "target": "Hey" },
        { "base": "What's up", "target": "Was geht" }
      ],
      "correctOptionIndex": 1
    }
  ]
}
`.trim();
}

export function createMultipleChoiceFromLessonInstructions(
  lessonTopic: string,
  lessonTitle: string,
  lessonSummary: string,
  lessonExplanation: string,
  exerciseCount: number,
  studentLevel: StudentLevel,
  baseLanguage: string,
  targetLanguage: string
): string {
  return `
${role(targetLanguage)}

${multipleChoiceFormat(baseLanguage, targetLanguage)}

${levelGuidance(studentLevel)}

Your Task: Create ${exerciseCount} multiple choice exercises based on the following ${targetLanguage} lesson.

Lesson Information:
Topic: ${lessonTopic}
Title: ${lessonTitle}
Summary: ${lessonSummary}
Content: ${lessonExplanation}

Requirements:
1. Extract key concepts and create questions that test understanding of the lesson
2. Create exactly ${exerciseCount} exercises (will be "exercises" array)
3. Questions should reinforce the main concepts taught in the lesson
4. All 4 options should be plausible, testing real comprehension
5. Match the student's level (${studentLevel}) in complexity
6. Both ${baseLanguage} and ${targetLanguage} should sound natural

Output Format:
Return a JSON object with:
- "exercises": An array of exercise objects

Example structure:
{
  "exercises": [
    {
      "question": {
        "base": "Which sentence correctly uses the past tense?",
        "target": "Welcher Satz verwendet die Vergangenheitsform richtig?"
      },
      "options": [
        { "base": "I go to school", "target": "Ich gehe zur Schule" },
        { "base": "I went to school", "target": "Ich ging zur Schule" },
        { "base": "I am going to school", "target": "Ich gehe gerade zur Schule" },
        { "base": "I will go to school", "target": "Ich werde zur Schule gehen" }
      ],
      "correctOptionIndex": 1
    }
  ]
}
`.trim();
}

// SENTENCE CREATION EXERCISES

function sentenceCreationFormat(baseLanguage: string, targetLanguage: string): string {
  return `Sentence Creation Exercise Format: Each exercise should have:
- "prompt": A prompt object with "base" (${baseLanguage}) and "target" (${targetLanguage}) - instructions for what sentence to create
- "referenceAnswer": A good example answer in ${targetLanguage}
- "context": Optional additional context or constraints for the exercise

The student will write a sentence based on the prompt, and AI will judge if it's correct (even if different from the reference answer).
Make prompts clear and specific enough that there's an objectively correct way to respond.`;
}

export function createSentenceCreationFromPromptInstructions(
  topic: string,
  exerciseCount: number,
  studentLevel: StudentLevel,
  baseLanguage: string,
  targetLanguage: string
): string {
  return `
${role(targetLanguage)}

${sentenceCreationFormat(baseLanguage, targetLanguage)}

${levelGuidance(studentLevel)}

Your Task: Create ${exerciseCount} sentence creation exercises about "${topic}".

Requirements:
1. Generate a suitable title for this exercise set (will be "title" field)
2. Create exactly ${exerciseCount} exercises (will be "exercises" array)
3. Each prompt should be clear and specific about what to write
4. Prompts should test practical writing skills in ${targetLanguage}
5. Reference answers should be natural and appropriate for the level
6. Exercises should cover different aspects of the topic
7. Match the student's level (${studentLevel}) in complexity and vocabulary

Output Format:
Return a JSON object with:
- "title": A short, descriptive title (string)
- "exercises": An array of exercise objects

Example structure:
{
  "title": "${targetLanguage} ${topic} Writing Practice",
  "exercises": [
    {
      "prompt": {
        "base": "Write a sentence introducing yourself and saying where you're from",
        "target": "Schreibe einen Satz, in dem du dich vorstellst und sagst, woher du kommst"
      },
      "referenceAnswer": "Ich heiße Maria und ich komme aus Spanien.",
      "context": "Use present tense and include your name and country"
    }
  ]
}
`.trim();
}

export function createSentenceCreationFromLessonInstructions(
  lessonTopic: string,
  lessonTitle: string,
  lessonSummary: string,
  lessonExplanation: string,
  exerciseCount: number,
  studentLevel: StudentLevel,
  baseLanguage: string,
  targetLanguage: string
): string {
  return `
${role(targetLanguage)}

${sentenceCreationFormat(baseLanguage, targetLanguage)}

${levelGuidance(studentLevel)}

Your Task: Create ${exerciseCount} sentence creation exercises based on the following ${targetLanguage} lesson.

Lesson Information:
Topic: ${lessonTopic}
Title: ${lessonTitle}
Summary: ${lessonSummary}
Content: ${lessonExplanation}

Requirements:
1. Extract key concepts and create prompts that practice the lesson's content
2. Create exactly ${exerciseCount} exercises (will be "exercises" array)
3. Prompts should be clear and test understanding of the lesson
4. Reference answers should demonstrate the concepts from the lesson
5. Match the student's level (${studentLevel}) in complexity
6. Exercises should reinforce what was taught in the lesson

Output Format:
Return a JSON object with:
- "exercises": An array of exercise objects

Example structure:
{
  "exercises": [
    {
      "prompt": {
        "base": "Write a sentence using the verb 'to have' in past tense",
        "target": "Schreibe einen Satz mit dem Verb 'haben' in der Vergangenheit"
      },
      "referenceAnswer": "Ich hatte gestern einen schönen Tag.",
      "context": "Use the lesson's grammar point about past tense"
    }
  ]
}
`.trim();
}

// SENTENCE JUDGING

export function judgeSentenceInstructions(
  prompt: string,
  promptBase: string,
  referenceAnswer: string,
  context: string | undefined,
  userAnswer: string,
  studentLevel: StudentLevel,
  baseLanguage: string,
  targetLanguage: string
): string {
  return `
Your Role: You are a helpful and encouraging language teacher evaluating a student's ${targetLanguage} sentence.

Student Level: ${studentLevel}

Exercise Prompt (${targetLanguage}): ${prompt}
Exercise Prompt (${baseLanguage}): ${promptBase}
${context ? `Context/Constraints: ${context}` : ''}

Reference Answer (example): ${referenceAnswer}

Student's Answer: ${userAnswer}

Your Task: Evaluate the student's sentence and provide constructive feedback.

Evaluation Criteria:
1. Does it answer the prompt correctly?
2. Is the grammar correct for their level?
3. Is the vocabulary appropriate and used correctly?
4. Is the sentence structure natural in ${targetLanguage}?
5. Are there spelling errors?

IMPORTANT: The student's answer does NOT need to match the reference answer exactly. The reference is just ONE possible correct answer. The student can use different words, structure, or approach and still be fully correct.

Scoring Guide:
- 100: Perfect or near-perfect answer
- 80-99: Good answer with minor errors (small grammar/spelling mistakes)
- 60-79: Acceptable answer but with notable errors (grammar issues but understandable)
- 40-59: Partially correct but significant problems (unclear meaning or major grammar errors)
- 20-39: Wrong approach or many errors (doesn't properly address prompt)
- 0-19: Completely incorrect or nonsensical

Output Format:
Return a JSON object with:
- "score": A number from 0-100
- "feedback": A clear, encouraging explanation in ${baseLanguage}

Your feedback should:
- Start with what they did well
- Explain any errors clearly
- Suggest corrections if needed
- Be encouraging and supportive
- Be concise (2-4 sentences)

Example output:
{
  "score": 85,
  "feedback": "Great work! Your sentence is grammatically correct and answers the prompt well. Just watch the word order after 'because' - in German, the verb goes to the end of that clause. Try: 'weil ich müde war' instead of 'weil ich war müde'."
}
`.trim();
}
