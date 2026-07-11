# Takeflow

[English](README.md) | **Русский**

**Takeflow — локальная AI-video студия для сцен, дублей и очередей, созданная Игорем Олеговичем Крамером / IOKRAMER.**

Takeflow — локальное приложение для Windows и macOS, которое помогает организовывать проекты и генерировать видео через Segmind Seedance API. Интерфейс открывается в браузере, а проекты и история остаются на компьютере пользователя.

Текущий релиз: **0.1.2 beta** (`v0.1.2-beta`).

## Скачать для Windows

Откройте страницу [Takeflow 0.1.2 beta](https://github.com/KramerIgor/takeflow/releases/tag/v0.1.2-beta):

1. Скачайте `TakeflowSetup-*.exe`.
2. Запустите установщик.
3. При необходимости оставьте создание ярлыка включённым.
4. Запустите Takeflow с рабочего стола или из меню «Пуск».

Python, Node.js, npm и Git не требуются. Beta-установщик пока не подписан цифровым сертификатом, поэтому Windows SmartScreen может запросить дополнительное подтверждение.

Подробности: [руководство пользователя Windows](docs/USER_GUIDE_RU.md).

## Скачать для macOS

В релизе доступны два готовых образа:

- `Takeflow-*-macOS-AppleSilicon.dmg` — для Mac с M1, M2, M3, M4 и более новыми чипами Apple.
- `Takeflow-*-macOS-Intel.dmg` — для Mac с процессором Intel.

Откройте DMG и перетащите **Takeflow** в **Applications / Программы**. Python, Homebrew, Node.js, Git и терминал не требуются.

Учебная beta-версия не зарегистрирована и не нотарифицирована Apple. При первом запуске потребуется один раз открыть **Системные настройки → Конфиденциальность и безопасность** и нажать **Всё равно открыть / Open Anyway**. Подробности: [руководство пользователя macOS](docs/MACOS_USER_GUIDE_RU.md).

## Возможности

- независимые проекты и выбор корневой папки;
- одиночные генерации с компактной историей справа;
- очередь генераций и отдельная история очереди;
- последовательный запуск или ограниченные параллельные волны (1–10 независимых задач); цепочки продолжения всегда соблюдают порядок родитель → потомок;
- импорт задач из CSV;
- изображения, видео и аудио в качестве референсов интерфейса;
- ограничения длительности, разрешения и количества референсов в зависимости от модели;
- предварительная оценка стоимости перед отправкой;
- сохранение промпта при обновлении истории;
- полноценный интерфейс RU/EN;
- обязательное подтверждение перед платной генерацией.

Сам Takeflow работает локально, но генерация видео использует внешний Segmind API и может расходовать платный баланс.

## Первый запуск

1. Откройте вкладку **Проекты**.
2. Введите API-ключ Segmind.
3. Оставьте стандартную папку `outputs/MyFirstProject` рядом с Windows-приложением или выберите другую доступную для записи корневую папку.
4. Создайте или выберите проект.
5. Перейдите в **Одиночную генерацию** или **Очередь**.

API-ключ хранится локально в `.env`, который исключён из Git. Никогда не публикуйте этот файл.

## Разработка на Windows

Требования:

- Windows 10/11 x64;
- Python 3.12;
- Git.

~~~powershell
git clone https://github.com/KramerIgor/takeflow.git
Set-Location -LiteralPath '.\takeflow'
py -3.12 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
Copy-Item '.env.example' '.env'
& '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 7860
~~~

Откройте `http://127.0.0.1:7860`.

Безопасные проверки:

~~~powershell
& '.\.venv\Scripts\python.exe' -m compileall app scripts takeflow_launcher.py
& '.\.venv\Scripts\python.exe' -u scripts\check_stage11_final_diagnostics.py
& '.\.venv\Scripts\python.exe' -u scripts\check_release_readiness.py
~~~

Проверки используют dry-run и синтетические данные и не должны отправлять платные генерации.

## Сборка Windows installer

Установите Inno Setup 6 и PyInstaller, затем выполните:

~~~powershell
& '.\.venv\Scripts\python.exe' -m pip install pyinstaller
powershell -NoProfile -ExecutionPolicy Bypass -File '.\scripts\build_windows_installer.ps1'
~~~

Результат:

~~~text
dist\installer\TakeflowSetup-0.1.2beta.exe
~~~

## Сборка пакетов macOS

macOS-пакеты должны собираться на macOS. Поддерживаемые Apple Silicon и Intel сборки автоматически выполняются GitHub Actions. Локальная команда для разработчика на Mac:

~~~bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pyinstaller
.venv/bin/python scripts/check_macos_release.py
PATH="$PWD/.venv/bin:$PATH" bash scripts/build_macos_dmg.sh "$(uname -m)"
~~~

Приложение подписывается ad-hoc для целостности bundle, но не является нотарифицированным Apple.

## Документация

- [Руководство Windows на русском](docs/USER_GUIDE_RU.md)
- [Windows User Guide in English](docs/USER_GUIDE.md)
- [Руководство macOS на русском](docs/MACOS_USER_GUIDE_RU.md)
- [macOS User Guide in English](docs/MACOS_USER_GUIDE.md)
- [Инструкция для агентов и разработчиков](docs/AGENT_GUIDE.md)
- [Текущее состояние проекта](docs/PROJECT_STATE.md)
- [Правила агентов](AGENTS.md)

## Безопасность и приватность

Репозиторий исключает:

- `.env` и API-ключи;
- виртуальные окружения и локальные runtime;
- SQLite-базы и состояние активного проекта;
- сгенерированные видео, результаты и архивы запусков;
- логи, кэш и временные файлы;
- скачанные модели и checkpoints.

Не размещайте секреты в issues, скриншотах, логах и release assets.

## Автор

Создано **Игорем Олеговичем Крамером / IOKRAMER**.

Лицензия открытого исходного кода пока не объявлена. Публичная доступность исходников сама по себе не предоставляет права повторного использования или распространения.
