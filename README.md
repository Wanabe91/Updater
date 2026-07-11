# Updater

AI-апдейтер зависимостей с миграцией кода. Сканирует проект, находит устаревшие
пакеты по реестрам (PyPI, npm, crates.io, Go proxy, Maven Central), безопасно
обновляет манифесты с бэкапами и откатом, предлагает альтернативы и мигрирует
код через LLM. История — в SQLite.

## Установка

```bash
pip install -e ".[dev]"
```

## Команды

```bash
updater scan run [PATH]              # найти зависимости (5 экосистем)
updater scan list-parsers            # список парсеров

updater update check [PATH]          # какие пакеты устарели
updater update apply [PATH] --dry-run  # показать diff манифестов
updater update apply [PATH]          # обновить манифесты (с бэкапом)
updater update rollback [PATH]       # откатить последнее обновление

updater suggest run [PATH] [-P pkg]  # AI-альтернативы зависимостям
updater migrate run [PATH] -P old -t new [--dry-run]  # AI-миграция кода
updater migrate rollback [PATH]      # откатить миграцию

updater tree show [PATH] [-d N] [--outdated]  # дерево зависимостей (PyPI)
updater history log [PATH]           # история обновлений
updater history deps [PATH]          # последний снапшот зависимостей
```

## Что читается и что обновляется

| Экосистема | Читается | Обновляется |
|---|---|---|
| Python | requirements.txt, pyproject.toml, Pipfile, setup.cfg | requirements.txt, pyproject.toml |
| Node.js | package.json, package-lock.json, yarn.lock, pnpm-lock.yaml | package.json |
| Rust | Cargo.toml, Cargo.lock | Cargo.toml |
| Go | go.mod, go.sum | go.mod |
| Java | pom.xml, build.gradle(.kts) | — (только проверка версий) |

Лок-файлы не переписываются — после обновления манифеста перегенерируйте их
пакетным менеджером (`pip-compile`, `npm install`, `cargo update`, `go mod tidy`).

Пины (`==`) обновляются до последней стабильной версии; диапазоны (`^`, `~`,
`>=`, `~=`) — до последней версии внутри диапазона.

## Настройка

Переменные окружения (префикс `UPDATER_`, поддерживается `.env`):

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `UPDATER_OPENAI_API_KEY` | ключ для AI-команд (suggest, migrate) | — |
| `UPDATER_OPENAI_BASE_URL` | OpenAI-совместимый endpoint | ai.wormsoft.ru |
| `UPDATER_OPENAI_MODEL` | модель | zai/glm-5.1 |
| `UPDATER_DB_PATH` | путь к SQLite-базе | ~/.updater/updater.db |
| `UPDATER_MAX_DEPTH` | глубина обхода каталогов при сканировании | 10 |

Бэкапы хранятся в `<проект>/.updater/backups/`. Схема БД управляется alembic
(`app/db/alembic`), при первом запуске создаётся автоматически.

## Разработка

```bash
python -m pytest tests -q     # тесты (без сети — реестры и AI застаблены)
python -m ruff check app tests
```
