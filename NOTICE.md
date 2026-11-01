# NOTICE — сторонние компоненты

## Simple Kafka Adapter (simpleKafka1C)

Расширение подключается к Apache Kafka через внешнюю native-компоненту **Simple Kafka Connector 1C** (имя объекта AddIn: `simpleKafka1C`).

- Репозиторий: https://github.com/NuclearAPK/Simple-Kafka_Adapter
- В поставке расширения бинарь лежит в общем макете `KFK_Компонента` (в проекте использовалась сборка 1.10.0).
- Лицензии upstream: см. `LICENSE` / `COPYING` в репозитории NuclearAPK (в т.ч. Apache-2.0 и AGPL-3.0 — проверяйте применимую к вашей сборке).

Код расширения 1С (BSL, метаданные CFE, контракт JSON Schema) **не является** форком Simple Kafka Adapter: используется только API компоненты для connect / subscribe / poll / produce / commit.

## Платформа и типовые конфигурации

«1С:Предприятие», «Бухгалтерия предприятия» и «Бухгалтерия для Казахстана» — продукты фирмы «1С». Их исходники в публичную поставку расширения не включаются.
