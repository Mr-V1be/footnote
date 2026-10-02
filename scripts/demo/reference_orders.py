"""Reference set: orders on personal data, one correct and one with typical slips.

The organisations and people are fictional. The violations the flawed order
carries are listed in backend/demo/reference/labels.yaml.
"""

from __future__ import annotations

from model import DemoDocument, Para, Style, Table, paras

ORDER_CORRECT = DemoDocument(
    path="reference/prikaz-severnyy-veter.docx",
    elements=(
        Para("ООО «Северный ветер»", Style.CENTER),
        Para("ПРИКАЗ", Style.TITLE),
        Table(rows=(("12.01.2026", "№ 3-ОД"),), header=False, borders=False),
        Para("г. Санкт-Петербург", Style.CENTER),
        Para(
            "Об утверждении Политики в отношении обработки персональных данных",
            Style.PLAIN,
        ),
        Para(
            "Во исполнение части 2 статьи 18.1 Федерального закона от 27.07.2006 № 152-ФЗ "
            "«О персональных данных» ПРИКАЗЫВАЮ:",
            Style.BODY,
        ),
        *paras(
            Style.CLAUSE,
            "1. Утвердить Политику в отношении обработки персональных данных (приложение).",
            "2. Назначить ответственным за организацию обработки персональных данных "
            "руководителя юридического отдела Белову Ольгу Николаевну.",
            "3. Начальнику отдела информационных технологий Гусеву Павлу Андреевичу "
            "опубликовать Политику на сайте Общества до 20.01.2026.",
            "4. Руководителям подразделений ознакомить работников с Политикой под подпись "
            "до 31.01.2026.",
            "5. Контроль за исполнением приказа оставляю за собой.",
        ),
        Para(
            "Приложение: Политика в отношении обработки персональных данных на 9 л. в 1 экз.",
            Style.PLAIN,
        ),
        Table(rows=(("Генеральный директор", "А.В. Морозов"),), header=False, borders=False),
    ),
)

# No registration number, a date in ISO form, no place, a heading that does
# not answer "about what?", sections in Roman numerals and the signature
# written surname first.
ORDER_FLAWED = DemoDocument(
    path="reference/prikaz-zarya.docx",
    elements=(
        Para("ООО «Заря»", Style.CENTER),
        Para("ПРИКАЗ", Style.TITLE),
        Para("2026-02-03", Style.CENTER),
        Para(
            "Назначение ответственного за обработку персональных данных гостей",
            Style.PLAIN,
        ),
        Para(
            "В связи с запуском программы лояльности ПРИКАЗЫВАЮ:",
            Style.BODY,
        ),
        *paras(
            Style.CLAUSE,
            "I. Назначить ответственным за организацию обработки персональных данных гостей "
            "управляющего сетью кафе Ершова Константина Львовича.",
            "II. Администраторам смен обеспечить хранение журнала бронирования в запираемом шкафу.",
            "III. Контроль за исполнением приказа оставляю за собой.",
        ),
        Table(rows=(("Директор", "Петров И.И."),), header=False, borders=False),
    ),
)
