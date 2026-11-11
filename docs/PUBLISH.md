# Как выложить на GitHub (безопасно)

Текущий рабочий монорепозиторий **нельзя** публиковать as-is:

1. В истории есть полные выгрузки типовых конфигураций 1С.
2. В tracked-файлах могут быть рабочие явки (например, правила доступа) и memory-bank с адресами окружения.
3. Рабочий монорепозиторий по-прежнему без `origin` на GitHub; публичная поставка — отдельный репозиторий `DmitrySkrypkin/1c-kafka-counterparties` (собирается скриптом `assemble-publish-tree.ps1`).

## Вариант A (рекомендуется): публичный репозиторий только поставки

Создайте **новый пустой** репозиторий на GitHub (public или internal), затем наполните его чистым деревом без истории монорепо.

### Состав

Скопировать:

```text
src/cfe/ИнтеграцияApacheKafka/          → cfe-rf/
src/cfe_bp_kz/ИнтеграцияApacheKafka/    → cfe-kz/
openspec/changes/archive/2026-11-09-counterparty-exchange-from-tz + outbound-from-1c → docs/
openspec/specs/counterparty-exchange/spec.md → docs/spec.md
docs/github-publication/README.md       → README.md
docs/github-publication/RELEASE_NOTES.md, NOTICE.md, LICENSE.template
docs/github-publication/dist/*.cfe      → dist/
```

Не копировать: `.dev.env`, `access.mdc`, `memory-bank/`, `src/cf/`, `src/cf_bp_kz/` (кроме CFE), `build/` (кроме собранного publish-дерева), `.cursor/`.

### Команды (пример)

Предпочтительно собрать дерево скриптом:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File docs/github-publication/assemble-publish-tree.ps1
# выход: build/github-publish/kafka-cfe-public
```

Далее синхронизировать содержимое `build/github-publish/kafka-cfe-public` в клон `DmitrySkrypkin/1c-kafka-counterparties`, commit, push, release:

```bash
gh release create cfe-kafka-counterparties-v1.1.0 -t "v1.1.0 — outbound counterparty exchange" -F RELEASE_NOTES.md \
  dist/IntegracijaApacheKafka-rf.cfe dist/IntegracijaApacheKafka-kz.cfe
```

Перед push обязательно прогоните поиск секретов. Бинарь компоненты в макете `KFK_Компонента` проверьте на лицензию upstream (NOTICE).

## Вариант B: private GitHub для всего монорепо

Только для закрытой организации заказчика.

1. Убрать из индекса / истории секреты (`access.mdc`, любые пароли).
2. Создать private repo.
3. Добавить `origin` и push выбранной ветки.
4. Не делать repository public без аудита.

Полная выгрузка БП на GitHub, даже private, должна быть согласована с лицензией поставщика конфигурации.

## Вариант C: только материалы без remote

Файлы в `docs/github-publication/` и пакет docx уже готовы к передаче. Remote создаёте вы.

## Что нужно от вас, чтобы агент завершил push

1. Имя org/user и имя репозитория (`DmitrySkrypkin/1c-kafka-counterparties`).
2. Public (только A) или Private (A или B).
3. Явное «создай репо и запушь».
4. Текст LICENSE организации (заменить template).
