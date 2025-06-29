# Telegram Bot Developer's Guide for Tasks

## Content
- [Database Structure](#database-structure)
- [Code Structure](#code-structure)
- [Chapter 2. Description of Classes, state machines, methods](#chapter-2-description-of-classes-state-machines-methods)
- [Chapter 3. How-the-bot-works](#chapter-3-how-the-bot-works)
- [User mode](#user-mode)
- [Administrator mode](#admin-mode)
- [Alert mode](#alert-mode)

---

# Chapter 1. The structure of the bot

## Database structure

### The users_tbl table
- **user_id**: int, Telegram user ID
- **chat_id**: int, group ID
- **username**: str, username of the user
- **full_name**: str, user name
- **status**: str, group status (administrator, member, etc.)
- **first_seen**: datetime, date of first appearance
- **last_seen**: datetime, date of last appearance

**Purpose:** Storing user information in groups.

### The tasks_tbl table is
**id**: int, the task ID
- **user_id**: int, the ID of the performing user
- **chat_id**: int, group ID
- **start_datetime**: datetime, date and time of the start of the task
- **end_datetime**: datetime, date and time of the end of the task
- **description**: str, task description
- **is_completed**: bool, whether the task is completed

**Purpose:** Storing tasks assigned to users in groups.

---

## Code structure

- **main.py ** — the main file of the bot, contains all the business logic, handlers, FSM, database work.
- **requirements.txt ** — project dependencies.
- **tasks_main.db** is an SQLite database.
- **.env** is an environment variables file. In the TOKEN=YOUR_TOKEN line, replace YOUR_TOKEN with your bot's token. Without spaces and brackets, as written.

### Basic classes and entities
- **User** is the ORM model of the user.
- **Task** is the ORM model of the task.
- **SimpleCalendar, SimpleCalendarCallback** — an inline calendar for selecting dates.
- **FSM (state machines):**
- TaskCreation — creating a task
- AdminViewTasks — viewing the user's tasks by the admin
- TaskStates — editing the task
- AdminSendMessageFSM — sending a message to the user on the task

### Basic methods and handlers
- **format_task_message** — formats the task and creates an inline keyboard
- **show_my_tasks_pm** — view user tasks
- **admin_choose_user_for_view, admin_view_selected_user_tasks** — admin's task view
- **new_task_start_pm, new_task_user_selected, ...** — FSM of task creation
- **edit_task_handler, process_edit_description, ...** — FSM of task editing
- **admin_sendmsg_start, admin_sendmsg_process** — FSM sending a message on a task
- **check_overdue_tasks, notify_task_deadlines** — background notification of overdue tasks

---

# Chapter 2. Description of classes, state machines, methods

## Classes
- **User** — describes the user, associated with tasks
- **Task** — describes the task, associated with the user
- **SimpleCalendar, SimpleCalendarCallback** — implements an inline calendar for selecting dates

## FSM (state machines)
- **TaskCreation**
- waiting_for_user — executor selection
  - waiting_for_start_date — select the start date
  - waiting_for_start_time — enter the start time
  - waiting_for_end_date — select the end date
  - waiting_for_end_time — enter the end time
  - waiting_for_description — entering a description
  - waiting_for_confirmation — confirmation
- **AdminViewTasks**
- waiting_for_user — selecting a user to view tasks
- viewing_tasks — viewing tasks of the selected user
- **TaskStates**
- editing_task_description — edit description
- editing_task_end_date — edit end date
- editing_task_end_time — edit end time
- **AdminSendMessageFSM**
  - waiting_for_text — waiting for the message text for the user

## Basic methods
- **format_task_message(task, for_admin)** — generates the task text and inline buttons
- **show_my_tasks_pm** — shows the user's tasks
- **admin_choose_user_for_view** — initiates the user's selection to view tasks
- **admin_view_selected_user_tasks** — shows the tasks of the selected user
- **new_task_start_pm** — start of task creation
- **new_task_user_selected** — artist selection
- **process_calendar_for_creation** — processing the inline calendar
- **new_task_start_time, new_task_end_time, new_task_description** — enter time and description
- **new_task_confirm** — confirmation of task creation
- **edit_task_handler, process_edit_description, process_edit_date, process_edit_end_time** — task editing
- **admin_sendmsg_start, admin_sendmsg_process** — sending a message to the user on a task
- **check_overdue_tasks, notify_task_deadlines** — background notification of overdue tasks

---

# Chapter 3. How the bot works

## User mode
- The user launches the bot via /start in the personal account.
- Gets a list of their tasks, can mark them completed, edit the description and deadlines.
- Receives personal notifications about new tasks and messages from the administrator.

## Admin mode
- The administrator selects the group via /admin (in the group).
- Can create tasks for any user from the list.
- Can view any user's tasks (select from the list).
- Can edit and delete tasks of any user.
- Can send a private message to the user on a specific task (with a quote of the task and a signature).

## Alert mode
- The bot periodically checks for overdue tasks.
- If the task is overdue and not completed, the bot sends a notification to the group chat mentioning the user.
- All notifications and messages are generated automatically, taking into account roles and context.