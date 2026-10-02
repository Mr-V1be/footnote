"""Reference set: short documents, each missing what the longer ones have.

They give every check at least one labelled violation, so its recall can be
measured. The organisations and people are fictional; the violations are
listed in backend/demo/reference/labels.yaml.
"""

from __future__ import annotations

from model import DemoDocument, Para, Style, Table, paras

# A website notice: no document type, date, place or approval; it does not
# name the categories of subjects, the legal grounds or the subject's rights.
POLICY_SITE = DemoDocument(
    path="reference/politika-sayt-uyut.docx",
    elements=(
        Para("Обработка персональных данных в интернет-магазине «Уют»", Style.TITLE),
        Para("1. Что мы обрабатываем и зачем", Style.HEADING),
        *paras(
            Style.CLAUSE,
            "1.1. ООО «Уют» (адрес: 344002, г. Ростов-на-Дону, ул. Пушкинская, д. 21) "
            "обрабатывает персональные данные, полученные через сайт uyut.example, в целях "
            "оформления заказа, его оплаты и доставки.",
            "1.2. Для заказа обрабатываются имя, телефон, адрес электронной почты и адрес "
            "доставки; для оплаты — сведения о платеже без данных банковской карты.",
        ),
        Para("2. Хранение и уничтожение", Style.HEADING),
        *paras(
            Style.CLAUSE,
            "2.1. Данные заказа хранятся 3 года после доставки, затем удаляются из базы "
            "без возможности восстановления в течение 30 дней; удаление фиксируется в журнале.",
            "2.2. Данные хранятся на серверах в Российской Федерации и за рубеж не передаются.",
            "2.3. Доставку выполняет ООО «Быстрая доставка», которому передаются имя, телефон и "
            "адрес доставки по договору поручения.",
        ),
        Para("3. Защита и обращения", Style.HEADING),
        *paras(
            Style.CLAUSE,
            "3.1. Доступ к данным имеют только работники службы заказов; соединение с сайтом "
            "шифруется, базы данных защищены паролями и резервируются ежедневно.",
            "3.2. Ответственным за организацию обработки назначен директор Лебедев Глеб "
            "Андреевич. Вопросы и запросы принимаются по адресу privacy@uyut.example, ответ "
            "даётся в течение 10 рабочих дней.",
        ),
    ),
)

# A newsletter consent ticked on a website: it names neither the subject nor
# the actions with the data and leaves no place for a signature.
CONSENT_NEWSLETTER = DemoDocument(
    path="reference/soglasie-rassylka.docx",
    elements=(
        Para("СОГЛАСИЕ", Style.TITLE),
        Para("на получение рекламной рассылки", Style.SUBTITLE),
        *paras(
            Style.BODY,
            "Отмечая поле «Хочу получать новости», я даю согласие ООО «Северный ветер», адрес: "
            "191002, г. Санкт-Петербург, ул. Рубинштейна, д. 15, на обработку моих "
            "персональных данных в целях направления мне сообщений об акциях и новинках.",
            "Обрабатываются имя и адрес электронной почты. Рассылку по поручению Оператора "
            "выполняет ООО «Почтовый голубь», адрес: 195027, г. Санкт-Петербург, "
            "Свердловская наб., д. 44.",
            "Согласие действует до его отзыва. Отозвать согласие можно по ссылке в любом письме "
            "рассылки или письмом на privacy@severnyy-veter.example.",
        ),
    ),
)

# A clause about personal data inside a services contract: security,
# documents on request and incidents are there; the data, the actions, the
# purposes and confidentiality are not.
ASSIGNMENT_CLAUSE = DemoDocument(
    path="reference/poruchenie-v-dogovore.docx",
    elements=(
        Para("ДОГОВОР № 22/2026", Style.TITLE),
        Para("возмездного оказания услуг", Style.SUBTITLE),
        Table(rows=(("г. Казань", "«16» февраля 2026 г."),), header=False, borders=False),
        Para(
            "ООО «Северный ветер» (Заказчик) и ООО «Колл-центр Плюс» (Исполнитель) заключили "
            "настоящий договор о нижеследующем.",
            Style.BODY,
        ),
        Para("1. Предмет договора", Style.HEADING),
        Para(
            "1.1. Исполнитель принимает входящие звонки покупателей Заказчика и передаёт "
            "Заказчику обращения в течение рабочего дня.",
            Style.CLAUSE,
        ),
        Para("2. Персональные данные", Style.HEADING),
        *paras(
            Style.CLAUSE,
            "2.1. Заказчик поручает Исполнителю обработку персональных данных покупателей.",
            "2.2. Исполнитель обеспечивает безопасность персональных данных и выполняет "
            "требования к их защите, установленные статьёй 19 Федерального закона "
            "№ 152-ФЗ «О персональных данных».",
            "2.3. По запросу Заказчика Исполнитель в течение 5 рабочих дней предоставляет "
            "документы, подтверждающие принятие мер по защите персональных данных.",
            "2.4. Исполнитель в течение 24 часов уведомляет Заказчика о неправомерной или "
            "случайной передаче персональных данных.",
        ),
        Table(
            rows=(("Заказчик", "Исполнитель"), ("А.В. Морозов", "Р.Ф. Галиев")),
            header=False,
            borders=False,
        ),
    ),
)

# An order with a number but no date and no signature.
ORDER_UNSIGNED = DemoDocument(
    path="reference/prikaz-uyut.docx",
    elements=(
        Para("ООО «Уют»", Style.CENTER),
        Para("ПРИКАЗ", Style.TITLE),
        Para("№ 12-ОД", Style.CENTER),
        Para("г. Ростов-на-Дону", Style.CENTER),
        Para("О назначении ответственного за обработку персональных данных", Style.PLAIN),
        Para(
            "Во исполнение статьи 22.1 Федерального закона от 27.07.2006 № 152-ФЗ "
            "«О персональных данных» ПРИКАЗЫВАЮ:",
            Style.BODY,
        ),
        *paras(
            Style.CLAUSE,
            "1. Назначить ответственным за организацию обработки персональных данных "
            "директора Лебедева Глеба Андреевича.",
            "2. Контроль за исполнением приказа оставляю за собой.",
        ),
    ),
)
