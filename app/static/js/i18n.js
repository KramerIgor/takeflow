// i18n and language switching
document.addEventListener("DOMContentLoaded", function () {
      const storageKey = "seedance_gui_language_v1";
      const switchButtons = Array.from(document.querySelectorAll("[data-lang-option]"));
      const translations = {
        ru: {
          app_subtitle: "Локальная AI-video студия для сцен, дублей и очередей",
          created_by: "Создано:",
          shutdown_server: "Выход",
          shutting_down: "Выключение...",
          confirm_shutdown_server: "Выключить локальный сервер Takeflow?",
          updates_title: "Обновления",
          update_available: "Есть обновления",
          update_checking: "Проверка...",
          update_check_failed: "Не удалось соединиться",
          update_current: "Последний релиз",
          check_updates: "Проверить",
          download_update: "Обновить",
          install_update: "Установить",
          download_starting: "Запуск скачивания...",
          download_progress: "Скачивание",
          download_complete: "Скачивание завершено.",
          download_failed: "Не удалось скачать",
          confirm_install_update: "Запустить установщик обновления и выключить Takeflow?",
          launching_installer: "Запускаю...",
          tab_projects: "Проекты",
          tab_single: "Одиночная генерация",
          tab_queue: "Очередь",
          projects_title: "Проекты",
          output_root: "Корневая папка",
          output_root_settings: "Корневая папка",
          output_root_settings_hint: "Выберите, где Takeflow хранит папки проектов. Существующие проекты не переносятся автоматически.",
          output_root_path_label: "Путь к папке",
          choose_output_root: "Выбрать...",
          choosing_output_root: "Выбор...",
          save_output_root: "Сохранить папку",
          output_root_save_hint: "Имя активного проекта останется тем же в выбранной корневой папке.",
          active_folder: "Активная папка",
          api_settings: "Настройки API",
          api_key_set: "API ключ задан",
          api_key_missing: "API ключ не задан",
          save_api: "Сохранить API",
          api_restart_hint: "Перезапусти GUI после смены ключа или модели.",
          project_list: "Папки проектов",
          create_project: "Создать проект",
          create: "Создать",
          single_title: "Одиночная генерация",
          single_hint: "Стартует в фоне и появляется в истории во время обработки.",
          history_title: "История",
          history_hint: "Здесь видны одиночные генерации, включая обработку и ошибки.",
          processing_notice: "Генерация выполняется. Нажми Обновить, чтобы проверить статус без очистки формы.",
          refresh_history: "Обновить",
          queue_controls: "Управление очередью",
          queue_controls_hint: "Запускай задачи, когда они готовы. Платные действия всегда требуют подтверждения.",
          queue_history: "Очередь / история",
          last_queued_task: "Последняя задача в очереди",
          task_folder: "Папка задачи",
          last_saved_draft: "Последний сохраненный черновик",
          draft_folder: "Папка черновика",
          reference_images: "Референс-изображения",
          settings_label: "Настройки",
          balance_label: "Баланс",
          balance_unavailable: "Недоступен",
          edit_prompt: "Редактировать промпт",
          edit_in_queue: "Редактировать в очереди",
          regenerate: "Перегенерировать",
          run_as_single_paid: "Запустить как одиночную (платно)",
          remove_from_queue: "Удалить из очереди",
          field_name: "Название",
          field_prompt: "Промпт",
          field_episode: "Эпизод",
          field_scene: "Сцена",
          field_model: "Модель",
          field_duration: "Длительность",
          field_resolution: "Разрешение",
          field_aspect_ratio: "Соотношение",
          field_seed: "Seed",
          field_generate_audio: "Генерировать аудио",
          field_return_last_frame: "Вернуть последний кадр",
          field_created: "Создано",
          field_completed: "Завершено",
          field_cost: "Стоимость",
          field_status: "Статус",
          field_reason: "Причина",
          field_error: "Ошибка",
          attached_references: "Референсы",
          add_files: "Добавить файлы",
          add_files_short: "Файл",
          no_refs_attached: "Референсы пока не добавлены.",
          no_attached_references: "Нет референсов",
          single_refs_hint: "Видео и аудио сохраняются в истории; в API пока отправляются только изображения.",
          queue_refs_hint: "Изображения отправляются в API. Видео и аудио сохраняются вместе с задачей.",
          prompt_drop_hint: "Перетащите сюда изображения, видео или аудио либо введите @, чтобы сослаться на прикрепленные файлы.",
          drop_files_choose: "Перетащите файлы сюда или выберите файлы.",
          add_to_queue_title: "Добавить в очередь",
          add_to_queue: "Добавить в очередь",
          save_draft: "Сохранить черновик",
          update_queue_item: "Обновить задачу",
          cancel_edit: "Отменить",
          queue_first_hint: "Сначала добавь задачи, потом запускай очередь.",
          run_single_paid: "Запустить одиночную генерацию (платно)",
          queue_progress: "Прогресс очереди",
          estimated_total_cost: "Предварительная стоимость",
          estimated_generation_cost: "Предварительная стоимость",
          cost_estimate_unavailable: "Нет оценки",
          cost_estimate_note: "Локальная оценка до запуска.",
          cost_estimate_text_image: "Текст/изображение, без реального списания.",
          cost_estimate_video: "Видео-референс, без реального списания.",
          stop_queue: "Остановить очередь",
          stop_queue_hint: "Останавливает задачи, которые еще не стартовали. Текущий запрос Segmind нельзя отменить локально.",
          resume_queue: "Возобновить очередь",
          resume_queue_hint: "Возвращает приостановленные задачи в очередь. Само по себе платную генерацию не запускает.",
          max_tasks_run: "Максимум задач за запуск",
          max_tasks: "Максимум задач",
          start_full_queue_paid: "Запустить всю очередь (платно)",
          start_full_queue_hint: "Запускает задачи по одной в фоне. Останавливается на первой ошибке.",
          run_next_summary: "Запустить только следующий элемент",
          start_next_paid: "Запустить следующий элемент (платно)",
          start_next_hint: "Обрабатывает только следующую задачу очереди.",
          last_queue_run: "Последний запуск очереди",
          processed_count: "Обработано",
          run_folder_result_files: "Папка run / файлы результата",
          elapsed_total: "Общее время",
          segmind_inference_time: "Время Segmind",
          batch_csv_import: "Пакетный импорт CSV",
          batch_csv_hint: "Загрузите CSV-файл, чтобы проверить его или создать задачи в очереди. Импорт не запускает платную генерацию.",
          required_columns: "Обязательные колонки:",
          optional_continuation_columns: "Дополнительные колонки продолжения:",
          csv_continuation_hint: "Строки с одинаковой группой продолжения связываются в порядке CSV: каждая следующая строка ждет предыдущую задачу и использует ее last_frame.png как референс.",
          csv_refs_separator_hint: "Используйте",
          csv_refs_separator_tail: "для разделения нескольких путей к референсам.",
          csv_file: "CSV-файл",
          preview_csv_import: "Проверить CSV (без задач)",
          create_queued_tasks_only: "Создать задачи в очереди (без платной генерации)",
          csv_import_actions_hint: "Проверка валидирует файл без создания задач. Подтверждение создает только задачи в очереди.",
          batch_import_report: "Отчет импорта CSV",
          field_mode: "Режим",
          rows_valid_rows: "Строки / валидные строки",
          created_tasks: "Создано задач",
          technical_task_ids: "ID задач",
          field_errors: "Ошибки",
          row_label: "Строка",
          status_completed: "завершено",
          status_processing: "в обработке",
          status_queued: "в очереди",
          status_failed: "ошибок",
          status_value_completed: "Завершено",
          status_value_processing: "В обработке",
          status_value_queued: "В очереди",
          status_value_failed: "Ошибка",
          status_value_cancelled: "Отменено",
          status_value_paused: "Приостановлено",
          status_value_draft: "Черновик",
          status_value_pending: "Ожидает",
          queue_loop_stop_requested: "Запрошена остановка для",
          queued_tasks_paused: "задач в очереди приостановлено. Текущая задача может еще завершиться.",
          queue_loop_running_for: "Очередь запущена для",
          page_refreshes_every: "Страница обновляется каждые",
          seconds: "секунд",
          queue_loop_stopped_error: "Очередь остановилась с ошибкой:",
          queue_loop_finished: "Очередь завершена:",
          processed_count_inline: "обработано",
          paid_confirm_title: "Это запустит платную генерацию. Продолжить?",
          ok: "OK",
          cancel: "Отмена",
          open_video: "Открыть видео",
          show_details: "Подробности",
          debug_files: "Debug / файлы",
          output_video: "Видео",
          technical_task_id: "Технический ID",
          queue_item: "Элемент очереди",
          active_project_label: "Активный",
          active_project_badge: "активный",
          api_key_label: "API-ключ",
          api_base_label: "API base URL",
          default_model_label: "Модель по умолчанию",
          no_projects_found: "Проекты пока не найдены.",
          last_generation_run: "Последний запуск генерации",
          run_folder: "Папка запуска",
          video_path: "Путь к видео",
          video_size: "Размер видео",
          bytes: "байт",
          unknown: "неизвестно",
          no_video_preview: "Нет превью видео",
          no_single_history: "Истории одиночных генераций пока нет.",
          no_queue_history: "Задач в очереди пока нет.",
          pagination_prev: "Назад",
          pagination_next: "Далее",
          refreshing: "Обновляю...",
          updated: "Обновлено",
          refresh_failed: "Не удалось обновить",
          opening: "Открываю...",
          opened: "Открыто",
          open_failed: "Не удалось открыть",
          remove: "Удалить",
          stored_history_not_api: "Сохранено в истории; в API не отправляется",
          placeholder_name: "Необязательное название, например opening-shot",
          placeholder_prompt: "Опишите видео-сцену...",
          placeholder_api_key: "Вставьте новый API-ключ Segmind",
          placeholder_output_root: "Например C:\\AI_OUTPUT или D:\\Takeflow",
          segmind_uploading_refs: "Загружаются референсы перед отправкой в Segmind. В панели Segmind задача появится после отправки.",
          segmind_preparing_submit: "Подготовка отправки в Segmind. В панели Segmind задача может появиться не сразу.",
          segmind_submitted: "Отправлено в Segmind",
          switch_project: "Переключить",
          delete_project: "Удалить",
          confirm_remove_queue: "Удалить эту задачу из очереди? Сгенерированные файлы не будут затронуты.",
          confirm_switch_project: "Переключить активный проект на {name}?",
          confirm_delete_project: "Удалить папку проекта {name}? Это удалит файлы внутри этого проекта.",
          confirm_create_queued_tasks: "Будут созданы только задачи в очереди. Платная генерация не запустится. Продолжить?",
          confirm_stop_queue: "Остановить очередь после текущей задачи? Еще не начатые задачи будут приостановлены.",
          confirm_start_full_queue: "Это запустит платные генерации Segmind для задач очереди одну за другой в фоне. Продолжить?",
          confirm_start_next_item: "Это запустит платную генерацию Segmind только для следующей задачи в очереди. Продолжить?",
          confirm_start_next_item: "Это запустит платную генерацию Segmind только для следующей задачи в очереди. Продолжить?"
        },
        en: {
          app_subtitle: "Local AI-video studio for scenes, takes, and queues",
          created_by: "Created by:",
          shutdown_server: "Quit",
          shutting_down: "Shutting down...",
          confirm_shutdown_server: "Shut down the local Takeflow server?",
          updates_title: "Updates",
          update_available: "Update available",
          update_checking: "Checking...",
          update_check_failed: "Unable to connect",
          update_current: "Latest release",
          check_updates: "Check",
          download_update: "Update",
          install_update: "Install",
          download_starting: "Starting download...",
          download_progress: "Downloading",
          download_complete: "Download complete.",
          download_failed: "Download failed",
          confirm_install_update: "Launch the update installer and shut down Takeflow?",
          launching_installer: "Launching...",
          output_root_settings: "Output root",
          output_root_settings_hint: "Choose where Takeflow stores project folders. Existing projects are not moved automatically.",
          output_root_path_label: "Folder path",
          choose_output_root: "Choose...",
          choosing_output_root: "Choosing...",
          save_output_root: "Save folder",
          output_root_save_hint: "The active project name stays the same in the selected root.",
          placeholder_output_root: "For example C:\\AI_OUTPUT or D:\\Takeflow",
          no_refs_attached: "No references attached yet.",
          drop_files_choose: "Drop files here or choose files.",
          add_files_short: "Add",
          remove: "Remove",
          stored_history_not_api: "Stored in history; not sent to API yet",
          run_as_single_paid: "Run as Single (paid)",
          status_value_completed: "Completed",
          status_value_processing: "Processing",
          status_value_queued: "Queued",
          status_value_failed: "Failed",
          status_value_cancelled: "Cancelled",
          status_value_paused: "Paused",
          status_value_draft: "Draft",
          status_value_pending: "Pending",
          unknown: "unknown",
          refreshing: "Refreshing...",
          updated: "Updated",
          refresh_failed: "Refresh failed",
          opening: "Opening...",
          opened: "Opened",
          open_failed: "Open failed",
          confirm_remove_queue: "Remove this queued item? No generated files will be touched.",
          confirm_switch_project: "Switch active project to {name}?",
          confirm_delete_project: "Delete project folder {name}? This removes files inside that project.",
          confirm_create_queued_tasks: "This will create queued tasks only. No paid generation will start. Continue?",
          confirm_stop_queue: "Stop the queue after the current processing task? Not-started queued tasks will be paused.",
          confirm_start_full_queue: "This will start paid Segmind generations for queued tasks one by one in the background. Continue?",
          confirm_start_next_item: "This will start a paid Segmind generation for only the next queued task. Continue?",
          estimated_generation_cost: "Estimated cost",
          cost_estimate_unavailable: "No estimate",
          cost_estimate_note: "Local estimate before submit.",
          cost_estimate_text_image: "Text/image estimate, no charge yet.",
          cost_estimate_video: "Video-reference estimate, no charge yet."
        }
      };

      const originalText = new Map();
      for (const node of document.querySelectorAll("[data-i18n]")) {
        originalText.set(node, node.textContent);
      }
      const originalPlaceholder = new Map();
      for (const node of document.querySelectorAll("[data-i18n-placeholder]")) {
        originalPlaceholder.set(node, node.getAttribute("placeholder") || "");
      }
      const originalDataPlaceholder = new Map();
      for (const node of document.querySelectorAll("[data-i18n-data-placeholder]")) {
        originalDataPlaceholder.set(node, node.dataset.placeholder || "");
      }

      function translate(key) {
        const lang = localStorage.getItem(storageKey) || "en";
        const dict = translations[lang] || {};
        const fallback = translations.en || {};
        return dict[key] || fallback[key] || key;
      }

      function interpolate(message, values) {
        return String(message || "").replace(/\{([a-zA-Z0-9_]+)\}/g, function (_, name) {
          return values && values[name] != null ? String(values[name]) : "";
        });
      }

      function statusKey(value) {
        const normalized = String(value || "")
          .trim()
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "_")
          .replace(/^_+|_+$/g, "");
        return normalized ? "status_value_" + normalized : "";
      }

      function statusLabel(value, lang) {
        const key = statusKey(value);
        if (!key) {
          return String(value || "");
        }
        const dict = translations[lang] || {};
        const fallback = translations.en || {};
        return dict[key] || fallback[key] || String(value || "");
      }

      function setLanguage(lang) {
        const dict = translations[lang] || {};
        document.documentElement.lang = lang;
        for (const node of document.querySelectorAll("[data-i18n]")) {
          const key = node.dataset.i18n;
          if (!originalText.has(node)) {
            originalText.set(node, node.textContent);
          }
          node.textContent = dict[key] || originalText.get(node) || node.textContent;
        }
        for (const node of document.querySelectorAll("[data-i18n-placeholder]")) {
          const key = node.dataset.i18nPlaceholder;
          if (!originalPlaceholder.has(node)) {
            originalPlaceholder.set(node, node.getAttribute("placeholder") || "");
          }
          node.setAttribute("placeholder", dict[key] || originalPlaceholder.get(node) || "");
        }
        for (const node of document.querySelectorAll("[data-i18n-data-placeholder]")) {
          const key = node.dataset.i18nDataPlaceholder;
          if (!originalDataPlaceholder.has(node)) {
            originalDataPlaceholder.set(node, node.dataset.placeholder || "");
          }
          node.dataset.placeholder = dict[key] || originalDataPlaceholder.get(node) || "";
        }
        for (const button of switchButtons) {
          button.classList.toggle("active", button.dataset.langOption === lang);
          button.setAttribute("aria-pressed", button.dataset.langOption === lang ? "true" : "false");
        }
        for (const title of document.querySelectorAll("[data-queue-label-en]")) {
          title.textContent = lang === "ru" ? title.dataset.queueLabelRu : title.dataset.queueLabelEn;
        }
        for (const node of document.querySelectorAll("[data-status-value]")) {
          node.textContent = statusLabel(node.dataset.statusValue, lang);
        }
        localStorage.setItem(storageKey, lang);
        document.dispatchEvent(new CustomEvent("seedance:language-changed", { detail: { lang: lang } }));
      }

      function confirmActionModal(message) {
        const modal = document.querySelector("[data-paid-confirm-modal]");
        if (!modal) {
          return Promise.resolve(window.confirm(message));
        }
        const title = modal.querySelector("#paid-confirm-title");
        const ok = modal.querySelector("[data-paid-confirm-ok]");
        const cancel = modal.querySelector("[data-paid-confirm-cancel]");
        if (!title || !ok || !cancel) {
          return Promise.resolve(window.confirm(message));
        }

        const previousTitle = title.textContent;
        const previousFocus = document.activeElement;
        title.textContent = message;
        modal.hidden = false;
        cancel.focus();

        return new Promise(function (resolve) {
          function cleanup(result) {
            modal.hidden = true;
            title.textContent = previousTitle;
            ok.removeEventListener("click", onOk);
            cancel.removeEventListener("click", onCancel);
            document.removeEventListener("keydown", onKeyDown);
            if (previousFocus && typeof previousFocus.focus === "function") {
              previousFocus.focus();
            }
            resolve(result);
          }
          function onOk() {
            cleanup(true);
          }
          function onCancel() {
            cleanup(false);
          }
          function onKeyDown(event) {
            if (event.key === "Escape") {
              event.preventDefault();
              cleanup(false);
            }
          }
          ok.addEventListener("click", onOk);
          cancel.addEventListener("click", onCancel);
          document.addEventListener("keydown", onKeyDown);
        });
      }

      function confirmAction(key, values) {
        return confirmActionModal(interpolate(translate(key), values || {}));
      }

      window.seedanceSetLanguage = setLanguage;
      window.seedanceTranslate = translate;
      window.seedanceConfirmAction = confirmAction;

      document.addEventListener("click", async function (event) {
        const trigger = event.target.closest("[data-confirm-key]");
        if (!trigger || trigger.dataset.confirmed === "1") {
          if (trigger) {
            delete trigger.dataset.confirmed;
          }
          return;
        }
        event.preventDefault();
        event.stopPropagation();
        if (trigger.form && (trigger.type || "").toLowerCase() === "submit" && !trigger.form.reportValidity()) {
          return;
        }
        const message = interpolate(translate(trigger.dataset.confirmKey), {
          name: trigger.dataset.confirmName || ""
        });
        const ok = await confirmActionModal(message);
        if (!ok) {
          return;
        }
        if (trigger.form && (trigger.type || "").toLowerCase() === "submit") {
          trigger.dataset.confirmed = "1";
          trigger.form.requestSubmit(trigger);
          window.setTimeout(function () {
            delete trigger.dataset.confirmed;
          }, 0);
        } else {
          trigger.dataset.confirmed = "1";
          trigger.click();
        }
      });

      for (const button of switchButtons) {
        button.addEventListener("click", function () {
          setLanguage(button.dataset.langOption || "en");
        });
      }

      setLanguage(localStorage.getItem(storageKey) || "en");
    });
