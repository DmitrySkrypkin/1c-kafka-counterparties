# Контракт счёта на оплату покупателю 1.0.0

Схемы описывают обмен счетами через `invoices` / `invoices.exchange` (change `product-invoice-exchange`):
- `headers.schema.json` — заголовки `invoice.created`, `invoice.updated`, `invoice.soft_delete`;
- `body.schema.json` — исходящий снимок счёта 1С;
- `body.portal.schema.json` — полный входящий снимок портала с обязательными `contract` и `responsible.uid`;
- `body.soft-delete.schema.json` — тело `invoice.soft_delete`;
- `status-headers.schema.json`, `status-body.schema.json` — статусы `invoice.exchange_*`.

Основа — список полей, согласованный 9 октября, и пример счёта от 07.09. Живых сообщений в `invoices` на 19.11.2026 нет: старые удалены по сроку хранения. Поэтому деньги, количество и `vat_percent` принимаются числом или строкой с числом, `released_at` — строкой с датой. До приёмки схема сверяется с первым живым счётом портала (PI-3).

Правила:
- `storehouse.uid` может быть `null`: тогда 1С берёт «Склад по умолчанию» из настроек контура, а если он не задан — `REQUIRED_FIELD_MISSING` по `storehouse.uid` (вопрос Q14; так приходят счета портала КЗ);
- заголовок `organization-id` обязателен: по нему счёт попадает в 1С РФ (`1`) или 1С КЗ (`5`); без него обе базы отвечают `REQUIRED_HEADER_MISSING`;
- для `sender=corp` обязателен `id`; исходящий счёт 1С идёт без `id`, `number` — номер 1С;
- ключ Kafka равен `uid` счёта у всех сообщений одного счёта, включая `invoice.soft_delete`;
- строки заменяются целиком, строка ссылается на товар по `uid`;
- признак «сумма включает НДС» вычисляется по суммам: `sum` равна сумме строк (НДС в цене) или сумме строк плюс `sum_vat` (НДС сверху), иначе `INVALID_FORMAT` по `sum`;
- ставку продажи задаёт `vat_percent` строки, `null` — без НДС; 1С не подбирает ставку по товару или организации;
- `is_marked_delete` — `true`/`false` или `1`/`0`;
- полный входящий счёт без договора (пропуск, null, пустой объект) даёт `REQUIRED_FIELD_MISSING` по `contract`;
- ответственный определяется по `responsible.uid` и полю «UID менеджера портала» пользователя базы; пустой UID даёт `REQUIRED_FIELD_MISSING`, неизвестный — `REFERENCE_NOT_FOUND`, неоднозначный — `DUPLICATE_CONFLICT`, путь `responsible.uid`;
- `status` и `sums` остаются вне загрузки;
- тип принимается в обоих написаниях: `invoice.updated` и `invoice_updated`.

Проверка:

```text
python validate_fixtures.py
```

## Каталог кодов

| Код | Когда |
| --- | --- |
| `REQUIRED_FIELD_MISSING` | Нет обязательного поля, например `uid` товара в строке |
| `REQUIRED_HEADER_MISSING` | Нет заголовка `organization-id` |
| `INVALID_FORMAT` | Поле в неверном формате или суммы счёта не сходятся |
| `UNSUPPORTED_VERSION` | Неподдерживаемая major-версия |
| `REFERENCE_NOT_FOUND` | Не найдены контрагент, договор, товар, склад, банковский счёт, валюта или ставка НДС |
| `DUPLICATE_CONFLICT` | По ключам найдено несколько счетов |
| `PERIOD_CLOSED` | Счёт в закрытом периоде, документ не изменён |
| `DEPENDENCY_FAILED` | Исходящий счёт: портал отклонил его контрагента или товар |
| `INTERNAL_ERROR` | Технический сбой обработки |

## Путь JSON

Путь — имена через точку от корня тела, элементы массива в скобках: `products[0].uid`, `storehouse.uid`, `currency.rcc`. Ошибка заголовка указывает имя заголовка: `organization-id`.
