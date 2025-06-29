- [**In Russian**](#Введение)
- [**In English**](#In-English)

## Введение

Этот бот предназначен для групповой работы с задачами в Telegram. Он поддерживает два режима: пользовательский и административный. Все данные хранятся в базе данных, задачи назначаются и контролируются администраторами.  

**Для запуска бота, необходимо:**  

- в файле .env в строке TOKEN=YOUR_TOKEN, замените YOUR_TOKEN на токен вашего бота. Без пробелов и скобок, как написано.
- установить в проект пакеты, прописанные в файле requirements.txt
- запустить файл бота main.py

---

## Основные роли
- **Пользователь** — может просматривать и редактировать только свои задачи.
- **Администратор** — может создавать задачи для других, просматривать и управлять задачами всех пользователей.

---

## Начало работы
1. **Добавьте бота в группу** и назначьте его администратором.
2. **Назначьте себя администратором группы** (если вы хотите управлять задачами).
3. **Запустите бота в личных сообщениях** командой `/start`.

---

## Основные команды

### /start (в личных сообщениях)
- Приветствие и отображение пользовательской клавиатуры.
- Просмотр своих задач.
- Управление своими задачами через кнопки.

### /admin (в группе)
- Проверка прав администратора.
- Открытие административной панели.
- Просмотр задач всех пользователей.
- Создание и назначение задач.

---

## Работа с задачами

### Для пользователя
- **Мои задачи** — просмотр всех своих задач, назначенных в разных группах.
- **Редактировать** — изменить описание или срок задачи.
- **Выполнить** — отметить задачу как выполненную.

### Для администратора
- **Новая задача** — создание задачи и назначение её пользователю из списка.
- **Просмотр задач пользователей** — выбор пользователя и просмотр его задач.
- **Редактировать/Удалить** — управление задачами любого пользователя.
- **Написать сообщение** — отправить личное сообщение пользователю по конкретной задаче.

---

## Оповещения
- Бот уведомляет о новых задачах в личных сообщениях.
- Администратор может отправить личное сообщение пользователю по задаче.
- Оповещения о просроченных задачах отправляются в групповой чат с упоминанием пользователя.

---

## Примеры сценариев

1. **Пользователь**:
   - Получает задачу — видит её в личке, может отметить как выполненную или отредактировать.
2. **Администратор**:
   - Создаёт задачу — выбирает пользователя из списка, указывает сроки и описание.
   - Просматривает задачи любого пользователя — выбирает пользователя, видит список задач, может управлять ими.
   - Пишет сообщение по задаче — выбирает задачу, пишет текст, пользователь получает сообщение с цитатой задачи.

---

## Важно
- Для корректной работы все участники должны хотя бы раз написать боту в личку (/start).
- Администраторские функции доступны только тем, кто является админом группы и выбрал группу через /admin.
- Если бот не может отправить личное сообщение пользователю, попросите его написать боту в личку. 

---

## Мои впечатления по проделанной работе.

Этот бот написан целиком и полностью Искусственным Интеллектом Cursor. Я не написал в ручную ни строчки кода.  
Понимаю, что полотно в 1200 строк очень тяжело в восприятии, но я сделал это намеренно, для того, чтобы протестировать следующим этапом, как AI Cursor-а справится с задачей по распределению такого большого файла с кодом по тематическим файлам (handlers, database, keyboard, filters и т.д)  
Если у него не выйдет, я сам, в ручную проделаю эту работу и бот будет идеальным.  
Бот полностью рабочий. Все функции выполняет на отлично. Это у меня был первый опыт работы с AI Cursor-a.  
Хочу выразить моё почтение и уважение разработчикам Cursor-a за такого прекрасного ассистента. Общение с ним ничем не отличалось
от общения с живым человеком.  

В благодарность разработчикам Cursor-a, я и опубликовал для общего пользования этого бота.

Всем добра и удачи с вашими проектами.  

---

## In English

## Introduction

This bot is designed for group work with tasks in Telegram. It supports two modes: user mode and administrative mode. All data is stored in a database, and tasks are assigned and controlled by administrators.  

**To launch the bot, you must:**  

- in the file .env in the TOKEN=YOUR_TOKEN line, replace YOUR_TOKEN with your bot's token. Without spaces and brackets, as written.
- install the packages specified in the file into the project requirements.txt
- run the bot file main.py

---

## Main roles
- **User** — can view and edit only their own tasks.
- **Administrator** — can create tasks for others, view and manage tasks for all users.

---

## Getting started
1. **Add the bot to the** group and appoint it as an administrator.
2. **Appoint yourself as the group administrator** (if you want to manage tasks).
3. **Launch the bot in private messages** with the command `/start'.

---

## Basic Commands

### /start (in private messages)
- Greeting and displaying a custom keyboard.
- View your tasks.
- Manage your tasks via buttons.

### /admin (in the group)
- Verification of administrator rights.
- Opening the administrative panel.
- View the tasks of all users.
- Create and assign tasks.

---

## Working with tasks

### For the user
- **My Tasks** — View all your tasks assigned in different groups.
- **Edit** — change the task description or deadline.
- **Complete** — mark the task as completed.

### For the administrator
- **New Task** — create a task and assign it to the user from the list.
- **View User Tasks** — Select a user and view their tasks.
- **Edit/Delete** — manage any user's tasks.
- **Write a message** — send a private message to the user for a specific task.

---

## Alerts
- The bot notifies about new tasks in private messages.
- The administrator can send a private message to the user about the task.
- Notifications about overdue tasks are sent to the group chat with the mention of the user.

---

## Examples of scenarios

1. **User**:
- Receives a task — sees it in the personal account, can mark it as completed or edit it.
2. **Administrator**:
   - Creates a task — selects a user from the list, specifies deadlines and a description.
   - Views any user's tasks — selects a user, sees a list of tasks, and can manage them.
   - Writes a message on a task — selects a task, writes a text, the user receives a message with a quote of the task.

---

## Important
- For correct operation, all participants must write to the bot at least once in the personal account (/start).
- Administrative functions are available only to those who are the group admin and have selected the group through /admin.
- If the bot cannot send a private message to the user, ask him to write to the bot in person. 

---

## My impressions of the work done.

This bot is written entirely by Cursor Artificial Intelligence. I haven't written a single line of code manually.  
I understand that a 1200-line canvas is very difficult to read, but I did it intentionally, in order to test in the next step how AI Cursor will cope with the task of distributing such a large code file into thematic files (handlers, database, keyboard, filters, etc.)  
If it doesn't work out, I'll do the job manually myself and the bot will be perfect.  
The bot is fully operational. Performs all functions perfectly. This was my first experience working with AI Cursor-A.  
I want to express my respect and respect to the Cursor-a developers for such a wonderful assistant. Communicating with him was no different
from communicating with a real person.  

As a thank you to the Cursor-a developers, I have published this bot for general use.

Good luck and good luck with your projects.