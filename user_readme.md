# AutoAlliance + Ozon

Руководство пользователя

## 1. Назначение

Программа автоматически:

- получает товары из Ozon;
- получает цены и остатки из Автоальянса;
- пересчитывает цену;
- обновляет цены и остатки в Ozon;
- получает новые отправления;
- разделяет отправления с несколькими товарами;
- автоматически закупает товары в Автоальянсе;
- предоставляет веб-интерфейс для работы курьера.

---

## 2. Первый запуск

Первичная настройка выполняется один раз.

Перейти в папку проекта:

```bash
cd autoalliance
```

Создать виртуальное окружение:

```bash
python -m venv venv
```

Активировать:

Windows:

```bash
.\venv\Scripts\activate
```

Linux:

```bash
source ./venv/bin/activate
```

Установить зависимости:

```bash
pip install -r .\requirements.txt
```

---

## 3. Добавление магазина Ozon

Для каждого магазина выполнить:

```bash
python -m src.scripts.ozon_add_shop
```

Потребуется:

- Client ID
- API Key
- Название магазина
- ID склада

ID склада находится:

<https://seller.ozon.ru/app/warehouse/>

Проверить список:

```bash
python -m src.scripts.ozon_list_shops
```

---

## 4. Импорт товаров Ozon

После добавления магазина выполнить:

Импорт списка товаров:

```bash
python -m src.scripts.ozon_import_products
```

Для одного магазина:

```bash
python -m src.scripts.ozon_import_products --shop "Название магазина"
```

---

## 5. Загрузка характеристик товаров

Выполнить:

```bash
python -m src.scripts.ozon_import_product_details
```

Для загрузки только новых:

```bash
python -m src.scripts.ozon_import_product_details --only-empty
```

Система загрузит:

- длину;
- ширину;
- высоту;
- комиссию категории;
- характеристики.

---

## 6. Загрузка базы Автоальянса

Импорт каталога:

```bash
python -m src.scripts.import_products path_to_XLSX
```

Пример:

```bash
python -m src.scripts.import_products .\data\AVTO-ALIANZ.xlsx
```

Лимит (ОПЦИОНАЛЬНО):

```bash
--limit INT
```

Затем дополнение данных для получения детальных характеристик:

```bash
python -m src.scripts.import_autoalliance_previews --only-empty
```

---

## 7. Создание администратора сайта

Выполняется один раз:

```bash
python -m src.scripts.create_admin --username admin --password 123456
```

---

## 8. Запуск сайта

Запуск:

```bash
uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

Открыть:

```text
http://127.0.0.1:8000
```

Вход:

Логин:

```text
admin
```

Пароль:

```text
123456
```

---

## 9. Запуск воркера

Основной процесс:

```bash
python -m src.scripts.run_worker
```

После запуска система автоматически:

Каждую минуту:

- проверяет новые отправления;
- разделяет групповые отправления;
- закупает товары Автоальянса;

Каждые 3 часа:

- получает товары Ozon;
- получает цены Автоальянса;
- получает остатки Автоальянса;
- пересчитывает цены;
- обновляет цены Ozon;
- обновляет остатки Ozon.

Останавливать воркер нельзя.

---

## 10. Ежедневная работа

Обычный порядок:

1. Проверить работу сайта.

2. Проверить работу воркера.

3. Проверить новые отправления.

4. Проверить логи:

```bash
logs/
```

Если ошибок нет — дополнительных действий не требуется.

---

## 11. Ручное изменение цены

Изменение цены товара:

```bash
python -m src.scripts.update_price_by_sku --article АРТИКУЛ --price НОВАЯ_ЦЕНА
```

Пример:

```bash
python -m src.scripts.update_price_by_sku --article A12345 --price 3490
```

---

## 12. Экстренное обнуление остатков

Все магазины:

```bash
python -m src.scripts.ozon_zero_stocks
```

Только один магазин:

```bash
python -m src.scripts.ozon_zero_stocks --shop_name "blamerz"
```

Проверить имя магазина:

```bash
python -m src.scripts.ozon_list_shops
```

---

## 13. Удаление магазина

Список:

```bash
python -m src.scripts.ozon_list_shops
```

Удаление:

```bash
python -m src.scripts.ozon_delete_shop
```

---

## 14. Возможные проблемы

Воркер показывает:

```text
candidates: 0
```

Причина:

товары отсутствуют в базе.

---

Появляются:

```text
no_match
```

Причина:

не найдено совпадение артикула между Ozon и Автоальянсом.

---

Появляется:

```text
TOO_MANY_REQUESTS
```

Причина:

Ozon временно ограничил запросы.

Повторить позже.

---

## 15. Перезапуск системы

Остановить:

CTRL+C

Запустить:

```bash
python -m src.scripts.run_worker
```

и:

```bash
uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```
