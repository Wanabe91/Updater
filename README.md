# Updater

AI-апдейтер зависимостей с миграцией кода. Сканирует проект, находит устаревшие
пакеты по реестрам (PyPI, npm, crates.io, Go proxy, Maven Central), безопасно
обновляет манифесты с бэкапами и откатом, предлагает альтернативы и мигрирует
код через LLM. История — в SQLite.

## Возможности

- **Сканирование** зависимостей в 5 экосистемах: Python, Node.js, Rust, Go, Java.
- **Проверка обновлений** по реестрам PyPI, npm, crates.io, Go proxy, Maven Central.
- **Безопасное обновление** манифестов: пины (`==`) → последняя стабильная версия;
  диапазоны (`^`, `~`, `>=`, `~=`) → последняя версия внутри диапазона.
- **Бэкапы и откат** — перед каждым изменением файлы копируются в `.updater/backups/`.
- **AI-альтернативы** — LLM подбирает пакеты-заменители с оценкой confidence.
- **AI-миграция кода** — переписывает импорты и вызовы API для `.py/.js/.ts/.go/.rs/.java`.
- **Дерево зависимостей** — транзитивное дерево Python через метаданные PyPI.
- **История** — все операции сохраняются в SQLite (`~/.updater/updater.db`).

## Установка

```powershell
.\install.ps1              # установка
.\install.ps1 -Force       # переустановка
```

Установщик сам:
- проверит Python >= 3.11;
- поставит `pipx`, если его нет, и добавит в PATH;
- установит пакет (команда `updater` появится глобально);
- перенесёт `UPDATER_*` из локального `.env` в `~/.updater/.env`, чтобы
  AI-команды работали из любой директории.

После завершения откройте **новый терминал** (чтобы обновился PATH) и проверьте:

```bash
updater --help
updater scan run <путь-к-любому-проекту>
updater suggest run <путь> -P typer   # проверка AI-команд
```

## Настройка

Конфигурация читается из двух источников (последний имеет приоритет):

1. **Глобальный** — `~/.updater/.env` (создаётся установщиком; работает из любой директории).
2. **Локальный** — `.env` в текущей рабочей директории (перекрывает глобальный).

Переменные окружения процесса имеют наивысший приоритет. Префикс `UPDATER_` обязателен.

```dotenv
UPDATER_OPENAI_API_KEY=ваш_ключ
UPDATER_OPENAI_BASE_URL=https://ai.wormsoft.ru/api/gpt
UPDATER_OPENAI_MODEL=zai/glm-5.1
```

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `UPDATER_OPENAI_API_KEY` | ключ для AI-команд (suggest, migrate) | — |
| `UPDATER_OPENAI_BASE_URL` | OpenAI-совместимый endpoint | `https://ai.wormsoft.ru/api/gpt` |
| `UPDATER_OPENAI_MODEL` | модель | `zai/glm-5.1` |
| `UPDATER_DB_PATH` | путь к SQLite-базе | `~/.updater/updater.db` |
| `UPDATER_MAX_DEPTH` | глубина обхода каталогов при сканировании | `10` |
| `UPDATER_BACKUP_DIR` | каталог для бэкапов | `<проект>/.updater/backups/` |

## Команды

`[PROJECT_PATH]` по умолчанию — текущая директория (`.`).

### scan — сканирование зависимостей

```bash
updater scan run [PROJECT_PATH]       # найти зависимости (5 экосистем)
updater scan list-parsers             # список доступных парсеров
```

### update — обновление версий

```bash
updater update check [PROJECT_PATH]       # какие пакеты устарели
updater update apply [PROJECT_PATH] --dry-run  # показать diff манифестов
updater update apply [PROJECT_PATH]            # обновить манифесты (с бэкапом)
updater update rollback [PROJECT_PATH]        # откатить последнее обновление
```

### suggest — AI-альтернативы

```bash
updater suggest run [PROJECT_PATH]                 # для всех зависимостей
updater suggest run [PROJECT_PATH] -P typer        # для конкретного пакета
updater suggest run [PROJECT_PATH] --max 20        # лимит пакетов
updater suggest run [PROJECT_PATH] --min-confidence 0.7
```

| Опция | Описание | По умолчанию |
|---|---|---|
| `-P, --package` | проанализировать конкретный пакет | — |
| `--max` | максимум пакетов для анализа | `10` |
| `--min-confidence` | минимальный confidence для показа | `0.8` |

### migrate — AI-миграция кода

```bash
updater migrate run [PROJECT_PATH] -P old -t new              # применить миграцию
updater migrate run [PROJECT_PATH] -P old -t new --dry-run   # показать изменения
updater migrate rollback [PROJECT_PATH]                       # откатить миграцию
```

| Опция | Описание |
|---|---|
| `-P, --package` (обязательный) | пакет, с которого мигрируем |
| `-t, --to` (обязательный) | пакет, на который мигрируем |
| `--dry-run` | показать изменения без применения |

Поддерживаемые расширения файлов: `.py .js .ts .go .rs .java`.

### tree — дерево зависимостей (PyPI)

```bash
updater tree show [PROJECT_PATH]                # дерево глубиной 3
updater tree show [PROJECT_PATH] -d 5          # глубже
updater tree show [PROJECT_PATH] -f httpx       # для конкретного пакета
updater tree show [PROJECT_PATH] --outdated     # подсветить устаревшие
```

| Опция | Описание | По умолчанию |
|---|---|---|
| `-d, --depth` | максимальная глубина дерева | `3` |
| `-f, --filter` | показать дерево для конкретного пакета | — |
| `--outdated` | подсветить устаревшие пакеты | — |

### history — история операций

```bash
updater history log [PROJECT_PATH]      # история обновлений и миграций
updater history log [PROJECT_PATH] -n 50  # больше записей
updater history deps [PROJECT_PATH]     # последний снапшот зависимостей
```

## Что читается и что обновляется

| Экосистема | Читается | Обновляется |
|---|---|---|
| Python | `requirements.txt`, `pyproject.toml`, `Pipfile`, `setup.cfg` | `requirements.txt`, `pyproject.toml` |
| Node.js | `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml` | `package.json` |
| Rust | `Cargo.toml`, `Cargo.lock` | `Cargo.toml` |
| Go | `go.mod`, `go.sum` | `go.mod` |
| Java | `pom.xml`, `build.gradle`, `build.gradle.kts` | — (только проверка версий) |

Лок-файлы не переписываются — после обновления манифеста перегенерируйте их
пакетным менеджером (`pip-compile`, `npm install`, `cargo update`, `go mod tidy`).

Пины (`==`) обновляются до последней стабильной версии; диапазоны (`^`, `~`,
`>=`, `~=`) — до последней версии внутри диапазона.

## Хранение данных

- **БД истории:** `~/.updater/updater.db` (SQLite, создаётся автоматически).
- **Бэкапы:** `<проект>/.updater/backups/<timestamp>-<tag>/` (теги `update` и
  `migrate` различают источники отката).
- **Схема БД** управляется Alembic (`app/db/alembic`), при первом запуске
  создаётся автоматически через `Base.metadata.create_all`.

## Пример сессии

```bash
# 1. Просканировать проект
updater scan run ./my-project

# 2. Проверить устаревшие пакеты
updater update check ./my-project

# 3. Посмотреть, что изменится
updater update apply ./my-project --dry-run

# 4. Применить обновления (создаст бэкап)
updater update apply ./my-project

# 5. Если что-то сломалось — откатить
updater update rollback ./my-project

# 6. Посмотреть историю
updater history log ./my-project
```

## Разработка

Для разработки пакет ставится напрямую (без pipx), чтобы инструменты
запускались из исходников:

```bash
pip install -e ".[dev]"
python -m pytest tests -q     # тесты (без сети — реестры и AI застаблены)
python -m ruff check app tests
python -m mypy app
```

### Структура проекта

```
app/
├── cli/            # Typer-команды (scan, update, suggest, migrate, tree, history)
├── core/           # Бизнес-логика (scanner, updater, version_resolver, migrator, analyzer, tree)
├── parsers/        # Парсеры манифестов (python, nodejs, rust, golang, java)
├── ai/             # AI-клиент и промпты (suggest, migrate)
├── db/             # SQLAlchemy-модели, репозиторий, Alembic-миграции
├── utils/          # Бэкапы и diff
└── config.py       # Настройки (pydantic-settings)
tests/              # Юнит-тесты (парсеры, core, ai, db, utils)
```

## Лицензия

MIT