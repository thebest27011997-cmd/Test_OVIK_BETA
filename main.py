import json
import math
import random
import re
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics import Color, Line, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.resources import resource_add_path
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.checkbox import CheckBox
from kivy.uix.label import Label
from kivy.uix.screenmanager import Screen, ScreenManager
from kivy.uix.textinput import TextInput


BASE = Path(__file__).resolve().parent
resource_add_path(str(BASE))

DATA_PATH = BASE / "data" / "questions.json"
KV_PATH = BASE / "testov.kv"

FONT_PATH = BASE / "fonts" / "Arial.ttf"
FONT_BOLD_PATH = BASE / "fonts" / "Arial-Bold.ttf"

APP_NAME = "ТехПрофи Beta"
ADMIN_CODE = "TEST_OVIK"

DEFAULT_NUM = 25
DEFAULT_MINUTES = 15
DEFAULT_PASS_PERCENT = 80


LabelBase.register(
    name="AppArial",
    fn_regular=str(FONT_PATH),
    fn_bold=str(FONT_BOLD_PATH),
)


def canon_list(value):
    if isinstance(value, list):
        parts = value
    else:
        parts = str(value or "").split(";")

    return {
        str(item).strip().casefold()
        for item in parts
        if str(item).strip()
    }


def is_correct(question, answer):
    qtype = question.get("type", "")

    if qtype == "несколько":
        return canon_list(answer) == canon_list(question.get("correct", []))

    acceptable = canon_list(question.get("correct", []))
    return str(answer or "").strip().casefold() in acceptable


def is_numeric_answer(question):
    correct = question.get("correct", [])
    if not isinstance(correct, list):
        correct = [correct]

    if not correct:
        return False

    pattern = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")
    return all(pattern.fullmatch(str(value).strip()) for value in correct)


def load_bank():
    with DATA_PATH.open("r", encoding="utf-8") as file:
        obj = json.load(file)

    sources = obj.get("sources", [])
    questions = obj.get("questions", [])

    if not isinstance(sources, list):
        raise ValueError("Поле 'sources' должно быть списком")

    if not isinstance(questions, list):
        raise ValueError("Поле 'questions' должно быть списком")

    return sources, questions


class AnswerRow(BoxLayout):
    selected = BooleanProperty(False)
    status = StringProperty("normal")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.checkbox = None

        with self.canvas.before:
            self.bg_color = Color(.99, .985, .97, 1)
            self.bg_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(12)],
            )

        with self.canvas.after:
            self.border_color = Color(.82, .76, .68, 1)
            self.border = Line(
                rounded_rectangle=(
                    self.x,
                    self.y,
                    self.width,
                    self.height,
                    dp(12),
                ),
                width=1.0,
            )

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            selected=self._update_visual,
            status=self._update_visual,
        )

    def attach_checkbox(self, checkbox):
        self.checkbox = checkbox
        self._update_visual()

    def _update_canvas(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.border.rounded_rectangle = (
            self.x,
            self.y,
            self.width,
            self.height,
            dp(12),
        )

    def _update_visual(self, *args):
        if self.status == "correct":
            self.bg_color.rgba = (.84, .95, .85, 1)
            self.border_color.rgba = (.08, .55, .20, 1)
            if self.checkbox:
                self.checkbox.color = (.05, .55, .18, 1)
            return

        if self.status == "wrong":
            self.bg_color.rgba = (.98, .84, .84, 1)
            self.border_color.rgba = (.86, .12, .10, 1)
            if self.checkbox:
                self.checkbox.color = (.90, .10, .08, 1)
            return

        if self.selected:
            self.bg_color.rgba = (.91, .85, .77, 1)
            self.border_color.rgba = (.55, .42, .29, 1)
            if self.checkbox:
                self.checkbox.color = (.48, .34, .22, 1)
        else:
            self.bg_color.rgba = (.99, .985, .97, 1)
            self.border_color.rgba = (.82, .76, .68, 1)
            if self.checkbox:
                self.checkbox.color = (.38, .38, .38, 1)

    def on_touch_down(self, touch):
        # Важно: для выбора ответа не нужно попадать точно в checkbox.
        # Нажатие на любую область строки выбирает/переключает ответ.
        if (
            self.collide_point(*touch.pos)
            and self.checkbox is not None
            and not self.checkbox.disabled
        ):
            if self.checkbox.group:
                self.checkbox.active = True
            else:
                self.checkbox.active = not self.checkbox.active
            return True

        return super().on_touch_down(touch)


class Login(Screen):
    admin_enabled = BooleanProperty(False)

    def on_pre_enter(self, *args):
        self.update_admin_state()

    def update_admin_state(self, *args):
        if "name" not in self.ids:
            return

        self.admin_enabled = self.ids.name.text.strip() == ADMIN_CODE

        if self.admin_enabled:
            self.ids.msg.text = "Административный режим доступен"
            self.ids.msg.color = (.10, .45, .15, 1)
        elif self.ids.msg.text == "Административный режим доступен":
            self.ids.msg.text = ""

    def open_settings(self):
        self.update_admin_state()

        if not self.admin_enabled:
            return

        self.ids.name.text = ""
        settings = self.manager.get_screen("settings")
        settings.load_values()
        self.manager.current = "settings"

    def start(self, mode):
        name = self.ids.name.text.strip()

        if not name:
            self.ids.msg.text = "Введите фамилию и инициалы"
            return

        if name == ADMIN_CODE:
            self.ids.msg.text = "Для тестирования введите ФИО тестируемого"
            return

        app = App.get_running_app()
        app.user = name
        app.mode = mode
        app.prepare_questions()

        if not app.questions:
            self.ids.msg.text = "Нет вопросов для выбранных источников"
            return

        self.ids.msg.text = ""

        test = self.manager.get_screen("test")
        test.begin()
        self.manager.current = "test"


class Test(Screen):
    question = StringProperty("")
    progress = StringProperty("")
    progress_ratio = NumericProperty(0.0)
    progress_percent = StringProperty("0%")
    timer = StringProperty("")
    source = StringProperty("")
    message = StringProperty("")
    answer_revealed = BooleanProperty(False)

    idx = NumericProperty(0)
    event = None
    input = None
    answer_rows = None

    def begin(self):
        app = App.get_running_app()

        self.idx = 0
        self.answer_revealed = False
        self.message = ""
        self.source = ""

        app.saved = ["" for _ in app.questions]
        app.seconds = int(app.test_minutes) * 60

        if self.event:
            self.event.cancel()
            self.event = None

        if app.mode == "контроль":
            self.event = Clock.schedule_interval(self.tick, 1)

        self.render()

    def tick(self, dt):
        app = App.get_running_app()
        app.seconds = max(0, app.seconds - 1)
        self.timer = f"{app.seconds // 60:02d}:{app.seconds % 60:02d}"

        if app.seconds <= 0:
            self.finish()
            return False

        return True

    def get_current_answer(self):
        app = App.get_running_app()

        if not app.questions:
            return ""

        question = app.questions[self.idx]
        qtype = question.get("type", "")

        if qtype == "текстовый":
            return self.input.text.strip() if self.input else ""

        selected = [
            option
            for option, checkbox, row in (self.answer_rows or [])
            if checkbox.active
        ]

        if qtype == "один":
            return selected[0] if selected else ""

        if qtype == "несколько":
            return "; ".join(selected)

        return ""

    def save_current(self):
        app = App.get_running_app()
        answer = self.get_current_answer()

        if 0 <= self.idx < len(app.saved):
            app.saved[self.idx] = answer

        return answer

    def has_answer(self):
        return bool(str(self.get_current_answer()).strip())

    def render(self):
        app = App.get_running_app()
        question = app.questions[self.idx]

        self.question = question.get("text", "")
        self.message = ""
        self.source = ""
        self.answer_revealed = False

        total = len(app.questions)
        current = self.idx + 1

        self.progress = f"Вопрос {current} из {total}"
        self.progress_ratio = current / total if total else 0
        self.progress_percent = f"{round(self.progress_ratio * 100)}%"

        if app.mode == "контроль":
            self.timer = f"{app.seconds // 60:02d}:{app.seconds % 60:02d}"
        else:
            self.timer = ""

        box = self.ids.answers
        box.clear_widgets()

        self.input = None
        self.answer_rows = []

        qtype = question.get("type", "")
        saved = app.saved[self.idx] if self.idx < len(app.saved) else ""

        if qtype == "текстовый":
            self.input = TextInput(
                text=saved,
                multiline=False,
                font_name="AppArial",
                font_size="18sp",
                size_hint_y=None,
                height=dp(58),
                input_type="number" if is_numeric_answer(question) else "text",
                write_tab=False,
                padding=(dp(14), dp(15)),
            )
            box.add_widget(self.input)
            return

        group_name = None
        if qtype == "один":
            group_name = f"single_{id(self)}_{self.idx}"

        saved_values = canon_list(saved)

        for option in question.get("options", []):
            option_text = str(option)

            row = AnswerRow(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(66),
                spacing=dp(8),
                padding=(dp(8), dp(7)),
            )

            checkbox = CheckBox(
                active=(option_text.casefold() in saved_values),
                group=group_name,
                size_hint_x=None,
                width=dp(46),
                color=(.38, .38, .38, 1),
            )

            label = Label(
                text=option_text,
                font_name="AppArial",
                font_size="16sp",
                color=(.08, .07, .06, 1),
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(48),
            )

            label.bind(width=self._resize_answer_label)
            label.bind(
                texture_size=lambda lbl, size, r=row:
                self._resize_answer_row(lbl, size, r)
            )

            checkbox.bind(
                active=lambda cb, value, r=row:
                self._checkbox_changed(r, value)
            )

            row.attach_checkbox(checkbox)
            row.selected = checkbox.active
            row.add_widget(checkbox)
            row.add_widget(label)

            box.add_widget(row)
            self.answer_rows.append((option_text, checkbox, row))

    def _checkbox_changed(self, row, value):
        row.selected = value

    def _resize_answer_label(self, label, width):
        label.text_size = (width, None)

    def _resize_answer_row(self, label, texture_size, row):
        label.height = max(dp(48), texture_size[1] + dp(16))
        row.height = label.height + dp(14)

    def show_source(self):
        app = App.get_running_app()
        question = app.questions[self.idx]

        source_name = str(question.get("source_name", "")).strip()
        source_ref = str(question.get("source", "")).strip()

        parts = [part for part in (source_name, source_ref) if part]
        self.source = "\n\n".join(parts)

    def show_correct(self):
        app = App.get_running_app()

        if app.mode != "обучение":
            return

        if not self.has_answer():
            self.message = "Сначала выберите или введите ответ"
            return

        self.save_current()
        self.answer_revealed = True
        self.message = ""

        question = app.questions[self.idx]
        qtype = question.get("type", "")
        correct = question.get("correct", [])

        if qtype in ("один", "несколько"):
            correct_values = canon_list(correct)

            for option, checkbox, row in self.answer_rows or []:
                key = option.strip().casefold()

                if key in correct_values:
                    row.status = "correct"
                elif checkbox.active:
                    row.status = "wrong"
                else:
                    row.status = "normal"

                checkbox.disabled = True

        elif qtype == "текстовый":
            answer = self.get_current_answer()

            if is_correct(question, answer):
                self.input.background_color = (.84, .95, .85, 1)
            else:
                self.input.background_color = (.98, .84, .84, 1)

                if isinstance(correct, list):
                    correct_text = "; ".join(str(x) for x in correct)
                else:
                    correct_text = str(correct)

                self.message = "Правильный ответ: " + correct_text

            self.input.disabled = True

        self.show_source()

    def next(self):
        app = App.get_running_app()

        if not self.has_answer():
            self.message = "Сначала выберите или введите ответ"
            return

        self.save_current()

        if self.idx >= len(app.questions) - 1:
            self.finish()
            return

        self.idx += 1
        self.render()

    def prev(self):
        app = App.get_running_app()

        self.save_current()

        if self.idx > 0:
            self.idx -= 1
            self.render()

    def finish(self):
        app = App.get_running_app()

        try:
            self.save_current()
        except Exception:
            pass

        if self.event:
            self.event.cancel()
            self.event = None

        score = sum(
            1
            for question, answer in zip(app.questions, app.saved)
            if is_correct(question, answer)
        )

        result = self.manager.get_screen("result")

        if app.mode == "обучение":
            result.text = (
                f"{app.user}\n\n"
                f"Обучение завершено\n\n"
                f"Правильных ответов: {score} из {len(app.questions)}"
            )
        else:
            required = math.ceil(
                len(app.questions) * int(app.pass_percent) / 100
            )
            status = "Тест пройден" if score >= required else "Тест не пройден"

            result.text = (
                f"{app.user}\n\n"
                f"Результат: {score} из {len(app.questions)}\n\n"
                f"Условие успешного прохождения: {int(app.pass_percent)}%\n\n"
                f"{status}"
            )

        self.manager.current = "result"


class Result(Screen):
    text = StringProperty("")


class AdminSettings(Screen):
    message = StringProperty("")

    def on_pre_enter(self, *args):
        self.load_values()

    def load_values(self):
        app = App.get_running_app()
        self.message = ""

        self.ids.question_count.text = str(int(app.question_count))
        self.ids.test_minutes.text = str(int(app.test_minutes))
        self.ids.pass_percent.text = str(int(app.pass_percent))

        Clock.schedule_once(self.build_source_rows, 0)

    def build_source_rows(self, *args):
        app = App.get_running_app()
        box = self.ids.sources_box
        box.clear_widgets()

        for source in app.source_catalog:
            source_id = source["id"]
            source_name = source["name"]

            row = BoxLayout(
                orientation="horizontal",
                size_hint_y=None,
                height=dp(116),
                spacing=dp(8),
                padding=(dp(8), dp(6)),
            )

            checkbox = CheckBox(
                active=(source_id in app.selected_sources),
                size_hint_x=None,
                width=dp(42),
                color=(.20, .16, .12, 1),
            )

            label = Label(
                text=source_name,
                font_name="Roboto",
                font_size="13sp",
                color=(.08, .07, .06, 1),
                halign="left",
                valign="middle",
            )
            label.text_size = (Window.width - dp(90), None)

            checkbox.bind(
                active=lambda cb, value, sid=source_id:
                self.on_source_checkbox(sid, value)
            )

            row.add_widget(checkbox)
            row.add_widget(label)
            box.add_widget(row)

        self.update_all_checkbox()

    def on_source_checkbox(self, source_id, active):
        app = App.get_running_app()

        if active:
            app.selected_sources.add(source_id)
        else:
            app.selected_sources.discard(source_id)

        self.update_all_checkbox()

    def update_all_checkbox(self):
        app = App.get_running_app()
        all_ids = set(app.available_sources)
        active = bool(all_ids) and all_ids.issubset(app.selected_sources)

        if self.ids.all_sources.active != active:
            self.ids.all_sources.active = active

    def toggle_all_sources(self, active):
        app = App.get_running_app()

        if active:
            app.selected_sources = set(app.available_sources)
        else:
            app.selected_sources = set()

        self.build_source_rows()

    def save_settings(self):
        app = App.get_running_app()

        if not app.selected_sources:
            self.message = "Выберите хотя бы один источник"
            return

        try:
            question_count = int(self.ids.question_count.text)
            test_minutes = int(self.ids.test_minutes.text)
            pass_percent = int(self.ids.pass_percent.text)

            if question_count <= 0 or test_minutes <= 0:
                raise ValueError

            if not 1 <= pass_percent <= 100:
                raise ValueError

        except ValueError:
            self.message = "Проверьте значения настроек"
            return

        app.question_count = question_count
        app.test_minutes = test_minutes
        app.pass_percent = pass_percent

        if app.save_user_settings():
            self.message = "Настройки сохранены"
        else:
            self.message = "Не удалось сохранить настройки"

    def go_back(self):
        self.manager.current = "login"


class TechProfiBetaApp(App):
    title = APP_NAME

    mode = StringProperty("")
    question_count = NumericProperty(DEFAULT_NUM)
    test_minutes = NumericProperty(DEFAULT_MINUTES)
    pass_percent = NumericProperty(DEFAULT_PASS_PERCENT)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.source_catalog = []
        self.available_sources = []
        self.selected_sources = set()

        self.pool = []
        self.questions = []
        self.saved = []

        self.user = ""
        self.seconds = 0
        self.settings_path = None

    def build(self):
        self.source_catalog, self.pool = load_bank()
        self.available_sources = [
            source["id"] for source in self.source_catalog
        ]
        self.selected_sources = set(self.available_sources)

        try:
            Window.softinput_mode = "below_target"
        except Exception:
            pass

        Builder.load_file(str(KV_PATH))

        manager = ScreenManager()
        manager.add_widget(Login(name="login"))
        manager.add_widget(Test(name="test"))
        manager.add_widget(Result(name="result"))
        manager.add_widget(AdminSettings(name="settings"))

        return manager

    def on_start(self):
        # Отдельный файл настроек для Beta,
        # чтобы старые source_id не ломали новую версию.
        self.settings_path = Path(self.user_data_dir) / "settings_beta.json"
        self.load_user_settings()

    def prepare_questions(self):
        filtered = [
            q
            for q in self.pool
            if q.get("source_id") in self.selected_sources
        ]

        random.shuffle(filtered)

        if self.mode == "контроль":
            count = min(int(self.question_count), len(filtered))
            self.questions = filtered[:count]
        else:
            self.questions = filtered

    def load_user_settings(self):
        self.question_count = DEFAULT_NUM
        self.test_minutes = DEFAULT_MINUTES
        self.pass_percent = DEFAULT_PASS_PERCENT
        self.selected_sources = set(self.available_sources)

        if not self.settings_path or not self.settings_path.exists():
            return

        try:
            data = json.loads(
                self.settings_path.read_text(encoding="utf-8")
            )

            self.question_count = max(
                1,
                int(data.get("question_count", DEFAULT_NUM)),
            )
            self.test_minutes = max(
                1,
                int(data.get("test_minutes", DEFAULT_MINUTES)),
            )
            self.pass_percent = max(
                1,
                min(100, int(data.get("pass_percent", DEFAULT_PASS_PERCENT))),
            )

            current = set(self.available_sources)
            saved = set(data.get("selected_sources", []))
            known = set(data.get("known_sources", []))

            selected = saved & current
            selected.update(current - known)

            if not known and not saved:
                selected = set(current)

            self.selected_sources = selected

        except Exception:
            self.selected_sources = set(self.available_sources)

    def save_user_settings(self):
        if not self.settings_path:
            self.settings_path = Path(self.user_data_dir) / "settings_beta.json"

        data = {
            "question_count": int(self.question_count),
            "test_minutes": int(self.test_minutes),
            "pass_percent": int(self.pass_percent),
            "selected_sources": sorted(self.selected_sources),
            "known_sources": sorted(self.available_sources),
        }

        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception:
            return False


if __name__ == "__main__":
    TechProfiBetaApp().run()
