# Контракт снимка номенклатуры 1.0.0

Схемы описывают обмен номенклатурой через `products` / `products.exchange` (change `product-invoice-exchange`).

- `headers.schema.json`, `body.schema.json` — `product.created` / `product.updated`, входящие от портала (`sender=corp`) и исходящие из 1С (`1c-rf`, `1c-kz`).
- `status-headers.schema.json`, `status-body.schema.json` — статусы `product.exchange_started`, `product.exchange_completed`, `product.exchange_failed`.

Основа — живые сообщения портала в `products`. По 30 последним сообщениям на 19.11.2026:
- тип уже `product.updated`, `version` `1.0.0`, отправитель `corp`;
- ключ Kafka равен `uid`;
- `timestamp-ms` — **13 цифр (миллисекунды)**, у контрагентов по ТЗ 10 (секунды). Для номенклатуры принимаются оба формата;
- поля тела: `id`, `uid`, `name`, `article`, `weight`, `country {id, oksm}`, `is_service`; `unit` портал пока не передаёт;
- есть заголовок `trace-id`, он не обязателен и не проверяется.

Правила тела:
- обязательны `uid` (GUID, 36 символов) и непустое `name`; `id` необязателен, 1С его не использует;
- `unit.okei` — строка из 3 цифр с ведущими нулями (`"796"` — шт, `"006"` — м);
- `is_service` — признак «услуга», нет поля — `false`;
- неизвестные поля игнорируются, в том числе `vat_percent`: ставку продажи задаёт строка счёта;
- исходящий снимок 1С без `id`, `country` в РФ — `{oksm}`, в КЗ — `null`.

Тип принимается в обоих написаниях: `product.updated` и `product_updated`. До переключения настройки `НовыеИменаТипов` 1С отправляет `product_created` и статусы `product_exchange_*`.

Проверка примеров и живых сообщений:

```text
python validate_fixtures.py
python validate_fixtures.py --live <файл с сообщениями Kafbat>
```

## Каталог кодов

| Код | Когда |
| --- | --- |
| `REQUIRED_FIELD_MISSING` | Нет обязательного поля или заголовка (`uid`, `name`) |
| `INVALID_FORMAT` | Поле в неверном формате, например `unit.okei` не из 3 цифр |
| `UNSUPPORTED_VERSION` | Неподдерживаемая major-версия |
| `REFERENCE_NOT_FOUND` | Код `unit.okei` нет в классификаторе ОКЕИ |
| `DUPLICATE_CONFLICT` | По `uid` найдено несколько товаров |
| `INTERNAL_ERROR` | Технический сбой обработки |

## Путь JSON

Путь поля — имена через точку от корня тела: `uid`, `name`, `unit.okei`, `country.oksm`. Ошибка заголовка указывает имя заголовка: `timestamp-ms`.
