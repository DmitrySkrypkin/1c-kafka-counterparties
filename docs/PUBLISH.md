# Как выложить на GitHub (безопасно)

Текущий рабочий монорепозиторий **нельзя** публиковать as-is:

1. В истории есть полные выгрузки типовых конфигураций 1С.
2. В tracked-файлах могут быть рабочие явки (например, правила доступа) и memory-bank с адресами окружения.
3. Remote сейчас только `bootstrap` → vanessa-bootstrap; своего `origin` нет. `gh` в PATH не найден.

## Вариант A (рекомендуется): публичный репозиторий только поставки

Создайте **новый пустой** репозиторий на GitHub (public или internal), затем наполните его чистым деревом без истории монорепо.

### Состав

Скопировать:

```text
src/cfe/ИнтеграцияApacheKafka/          → ИнтеграцияApacheKafka/
src/cfe_bp_kz/ИнтеграцияApacheKafka/    → ИнтеграцияApacheKafka-kz/
openspec/changes/counterparty-exchange-from-tz/*.md
openspec/changes/counterparty-exchange-from-tz/*.docx
docs/github-publication/README.md       → README.md (корень нового репо)
docs/github-publication/RELEASE_NOTES.md
docs/github-publication/NOTICE.md
docs/github-publication/LICENSE.template → LICENSE (заполнить)
```

Не копировать: `.dev.env`, `access.mdc`, `memory-bank/`, `src/cf/`, `src/cf_bp_kz/` (кроме CFE), `build/`, `.cursor/`.

### Команды (пример)

```bash
mkdir -p /tmp/kafka-1c-publish && cd /tmp/kafka-1c-publish
git init -b main

# пути от корня рабочего проекта AI
SRC="D:/04.Work/05.Курчаков/AI"
cp -R "$SRC/src/cfe/ИнтеграцияApacheKafka" ./ИнтеграцияApacheKafka
cp -R "$SRC/src/cfe_bp_kz/ИнтеграцияApacheKafka" ./ИнтеграцияApacheKafka-kz
mkdir -p docs
cp "$SRC/openspec/changes/counterparty-exchange-from-tz/"*.md docs/
cp "$SRC/openspec/changes/counterparty-exchange-from-tz/"*.docx docs/ 2>/dev/null || true
cp "$SRC/docs/github-publication/README.md" ./README.md
cp "$SRC/docs/github-publication/RELEASE_NOTES.md" .
cp "$SRC/docs/github-publication/NOTICE.md" .
cp "$SRC/docs/github-publication/LICENSE.template" ./LICENSE

# перед commit: поиск секретов
rg -i "password|пароль|itcs_pass|KAFKA_PASSWORD|nYDAj" . || true

git add .
git commit -m "$(cat <<'EOF'
Initial public release: ИнтеграцияApacheKafka 1.0.0 (counterparties)

EOF
)"

# создать репо на GitHub вручную или через gh, затем:
# git remote add origin https://github.com/<org>/<repo>.git
# git push -u origin main
# gh release create cfe-kafka-counterparties-v1.0.0 -F RELEASE_NOTES.md
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

1. Имя org/user и имя репозитория.
2. Public (только A) или Private (A или B).
3. Явное «создай репо и запушь» (сейчас `gh` не установлен — потребуется установка GitHub CLI или ручное создание + `git push`).
4. Текст LICENSE организации (заменить template).
