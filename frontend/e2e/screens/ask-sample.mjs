// A conversation for the screenshot of an answer while the stand has no
// model API key: the browser receives it in place of the API's reply. The
// quotes are verbatim from the stand's corpus of 152-FZ; the second question
// is answered honestly as "not found" (fines are not in 152-FZ).
const CONVERSATION_ID = "01a10000-0000-7000-8000-00000000a5c1";
const ASKED_AT = "2026-10-03T08:12:00Z";

export const SAMPLE_CONVERSATION = {
  id: CONVERSATION_ID,
  title: "Отзыв согласия работником",
  turns: [
    {
      id: "01a10000-0000-7000-8000-00000000a5c2",
      question: "Что делать, если работник отозвал согласие на обработку персональных данных?",
      status: "answered",
      answer:
        "Согласие можно отозвать [1]. После отзыва оператор обязан прекратить обработку " +
        "и, если данные больше не нужны для целей обработки, уничтожить их в срок не более " +
        "тридцати дней с даты поступления отзыва [2]. Продолжить обработку без согласия можно " +
        "только при основаниях, названных в законе [3].",
      citations: [
        {
          number: 1,
          actCode: "152-fz",
          anchor: "st-9/ch-2",
          citation: "ч. 2 ст. 9 152-ФЗ",
          quote:
            "Согласие на обработку персональных данных может быть отозвано субъектом персональных данных.",
        },
        {
          number: 2,
          actCode: "152-fz",
          anchor: "st-21/ch-5",
          citation: "ч. 5 ст. 21 152-ФЗ",
          quote: "в срок, не превышающий тридцати дней с даты поступления указанного отзыва",
        },
        {
          number: 3,
          actCode: "152-fz",
          anchor: "st-9/ch-2",
          citation: "ч. 2 ст. 9 152-ФЗ",
          quote:
            "оператор вправе продолжить обработку персональных данных без согласия субъекта " +
            "персональных данных при наличии оснований",
        },
      ],
      askedAt: ASKED_AT,
    },
    {
      id: "01a10000-0000-7000-8000-00000000a5c3",
      question: "Какой штраф грозит, если не уничтожить данные вовремя?",
      status: "not_found",
      answer: null,
      citations: [],
      askedAt: ASKED_AT,
    },
  ],
};

export async function answerWithSample(page) {
  await page.route("**/bff/api/v1/organizations/*/ask/status", (route) =>
    route.fulfill({
      json: { configured: true, languageModel: "sample", embeddingModel: "sample" },
    }),
  );
  await page.route("**/bff/api/v1/organizations/*/ask/conversations", (route) =>
    route.fulfill({
      json: [
        { id: CONVERSATION_ID, title: SAMPLE_CONVERSATION.title, updatedAt: ASKED_AT },
        {
          id: "01a10000-0000-7000-8000-00000000a5c4",
          title: "Срок ответа на запрос субъекта",
          updatedAt: "2026-10-01T10:00:00Z",
        },
      ],
    }),
  );
  await page.route(`**/bff/api/v1/organizations/*/ask/conversations/${CONVERSATION_ID}`, (route) =>
    route.fulfill({ json: SAMPLE_CONVERSATION }),
  );
  return CONVERSATION_ID;
}
