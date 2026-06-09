import json
import logging
from datetime import timedelta
from types import SimpleNamespace

from odoo import fields, http
from odoo.exceptions import AccessDenied
from odoo.http import request
from werkzeug.exceptions import Forbidden

from ..services.recommendations import EventRecommendationEngine


_logger = logging.getLogger(__name__)


class EventMindController(http.Controller):
    INTEREST_TAGS = [
        "Программирование",
        "Стартапы",
        "Искусство",
        "Маркетинг",
        "Дизайн",
        "AI и ML",
        "Аналитика данных",
        "Бизнес",
        "Психология",
        "Образование",
        "Спорт",
        "Нетворкинг",
    ]

    @staticmethod
    def _serialize_event_for_calendar(event):
        start_dt = fields.Datetime.to_datetime(event.date_start)
        end_dt = fields.Datetime.to_datetime(event.date_end or event.date_start)
        if not start_dt:
            return None

        return {
            "id": event.id,
            "title": event.name or "",
            "start": start_dt.isoformat(),
            "end": (end_dt or start_dt).isoformat(),
            "location": event.location or "",
            "url": event.source_url or "",
        }

    def _calendar_payload(self, events):
        calendar_events = []
        for event in events:
            serialized = self._serialize_event_for_calendar(event)
            if serialized:
                calendar_events.append(serialized)
        return json.dumps(calendar_events, ensure_ascii=False)

    def _authenticate(self, login, password):
        try:
            return request.session.authenticate(request.db, login, password)
        except TypeError:
            return request.session.authenticate(
                request.db,
                {"login": login, "password": password, "type": "password"},
            )

    def _extract_interest_values(self):
        selected = request.httprequest.form.getlist("interests")
        selected = [item.strip() for item in selected if item and item.strip()]
        return [item for item in selected if item in self.INTEREST_TAGS]

    @staticmethod
    def _extract_partner_interest_values(partner):
        raw = partner.em_interests or ""
        return [item.strip() for item in raw.split(",") if item.strip()]

    @staticmethod
    def _recommendations_for(user, events, top_k=6):
        if user._is_public():
            return []
        try:
            items = EventRecommendationEngine(top_k=top_k).recommend_for_user(user.sudo(), events.sudo())
        except Exception:
            _logger.exception("EventMind recommendations failed")
            return []
        return [SimpleNamespace(**item) for item in items]

    @staticmethod
    def _notification_items_for(user):
        if user._is_public():
            return []

        now = fields.Datetime.to_datetime(fields.Datetime.now())
        remind_until = now + timedelta(days=1)
        items = []

        for event in user.sudo().personal_event_ids:
            start_dt = fields.Datetime.to_datetime(event.date_start)
            if not start_dt or start_dt < now or start_dt > remind_until or event.status == "cancelled":
                continue

            hours_until = (start_dt - now).total_seconds() / 3600
            if hours_until <= 3:
                label = "Через несколько часов"
                message = "Событие начнется совсем скоро."
            else:
                label = "За день до события"
                message = "До мероприятия осталось меньше суток."

            items.append(
                SimpleNamespace(
                    event=event,
                    label=label,
                    message=message,
                    display_datetime=event.eventmind_display_datetime(),
                )
            )

        return sorted(items, key=lambda item: item.event.date_start or fields.Datetime.now())

    @staticmethod
    def _upcoming_events_domain():
        return [
            ("status", "!=", "cancelled"),
            ("date_start", ">=", fields.Datetime.now()),
        ]

    def _ensure_timepad_events_available(self):
        events = request.env["eventmind.event"].sudo()
        upcoming_timepad_count = events.search_count(
            self._upcoming_events_domain() + [("source", "=", "timepad")]
        )
        if upcoming_timepad_count:
            return

        try:
            events.import_timepad_json()
        except Exception:
            _logger.exception("EventMind Timepad JSON import failed")

    @http.route("/eventmind/admin/sync-timepad", type="http", auth="user", website=True)
    def sync_timepad_events(self, **kwargs):
        if not request.env.user.has_group("base.group_system"):
            raise Forbidden()

        request.env["eventmind.event"].sudo().import_timepad_json()
        return request.redirect("/eventmind/events")

    @http.route("/eventmind/events", type="http", auth="public", website=True)
    def eventmind_events(self, **kwargs):
        self._ensure_timepad_events_available()
        events = request.env["eventmind.event"].sudo().search(
            self._upcoming_events_domain(),
            order="date_start asc",
        )

        user_event_ids = []
        notification_items = []
        if not request.env.user._is_public():
            current_user = request.env.user.sudo()
            user_event_ids = current_user.personal_event_ids.ids
            notification_items = self._notification_items_for(current_user)

        return request.render(
            "eventmind.eventmind_events_page",
            {
                "events": events,
                "user_event_ids": user_event_ids,
                "notification_items": notification_items,
                "calendar_events_json": self._calendar_payload(events),
            },
        )

    @http.route("/eventmind/recommendations", type="http", auth="user", website=True)
    def eventmind_recommendations(self, **kwargs):
        self._ensure_timepad_events_available()
        user = request.env.user.sudo()
        events = request.env["eventmind.event"].sudo().search(
            self._upcoming_events_domain(),
            order="date_start asc",
        )
        recommendation_items = self._recommendations_for(user, events, top_k=12)
        selected_interests = self._extract_partner_interest_values(user.partner_id.sudo())

        return request.render(
            "eventmind.eventmind_recommendations_page",
            {
                "recommendation_items": recommendation_items,
                "selected_interests": selected_interests,
                "has_profile_data": bool(selected_interests or user.personal_event_ids),
                "notification_items": self._notification_items_for(user),
            },
        )

    @http.route("/eventmind/login", type="http", auth="public", website=True, methods=["GET", "POST"])
    def eventmind_login(self, **post):
        if request.httprequest.method == "GET":
            return request.render(
                "eventmind.eventmind_login_page",
                {
                    "error": "",
                    "notification_items": self._notification_items_for(request.env.user.sudo()),
                },
            )

        login = (post.get("login") or "").strip().lower()
        password = post.get("password") or ""
        error = ""

        if not login or not password:
            error = "Заполните email и пароль."
        else:
            try:
                uid = self._authenticate(login, password)
                if uid:
                    return request.redirect("/eventmind/cabinet")
                error = "Неверный email или пароль."
            except AccessDenied:
                error = "Неверный email или пароль."

        return request.render(
            "eventmind.eventmind_login_page",
            {
                "error": error,
                "login": login,
                "notification_items": self._notification_items_for(request.env.user.sudo()),
            },
        )

    @http.route("/eventmind/signup", type="http", auth="public", website=True, methods=["GET", "POST"])
    def eventmind_signup(self, **post):
        if request.httprequest.method == "GET":
            return request.render(
                "eventmind.eventmind_signup_page",
                {
                    "error": "",
                    "values": {},
                    "interest_tags": self.INTEREST_TAGS,
                    "notification_items": self._notification_items_for(request.env.user.sudo()),
                },
            )

        full_name = (post.get("full_name") or "").strip()
        login = (post.get("login") or "").strip().lower()
        password = post.get("password") or ""
        password_confirm = post.get("password_confirm") or ""
        age_raw = (post.get("age") or "").strip()
        gender = (post.get("gender") or "").strip()
        selected_interests = self._extract_interest_values()
        interests = ", ".join(selected_interests)

        values = {
            "full_name": full_name,
            "login": login,
            "age": age_raw,
            "gender": gender,
            "interests": selected_interests,
        }

        error = ""
        age = 0
        if not full_name or not login or not password:
            error = "ФИО, email и пароль обязательны."
        elif password != password_confirm:
            error = "Пароли не совпадают."
        else:
            if age_raw:
                try:
                    age = int(age_raw)
                except ValueError:
                    error = "Возраст должен быть числом."
                if age < 0 or age > 120:
                    error = "Возраст должен быть от 0 до 120."

        users = request.env["res.users"].sudo()
        if not error and users.search_count([("login", "=", login)]):
            error = "Пользователь с таким email уже существует."

        if error:
            return request.render(
                "eventmind.eventmind_signup_page",
                {
                    "error": error,
                    "values": values,
                    "interest_tags": self.INTEREST_TAGS,
                    "notification_items": self._notification_items_for(request.env.user.sudo()),
                },
            )

        portal_group = request.env.ref("base.group_portal")
        user = users.with_context(no_reset_password=True).create(
            {
                "name": full_name,
                "login": login,
                "email": login,
                "password": password,
                "groups_id": [(6, 0, [portal_group.id])],
            }
        )

        user.partner_id.sudo().write(
            {
                "name": full_name,
                "em_age": age,
                "em_gender": gender or False,
                "em_interests": interests,
            }
        )

        try:
            uid = self._authenticate(login, password)
        except AccessDenied:
            uid = False

        if uid:
            return request.redirect("/eventmind/cabinet")
        return request.redirect("/eventmind/login")

    @http.route("/eventmind/cabinet", type="http", auth="user", website=True, methods=["GET", "POST"])
    def eventmind_cabinet(self, **post):
        self._ensure_timepad_events_available()
        user = request.env.user.sudo()
        profile = user.partner_id.sudo()
        error = ""
        success = ""

        if request.httprequest.method == "POST":
            action = post.get("action")
            if action == "update_profile":
                full_name = (post.get("full_name") or "").strip()
                email = (post.get("email") or "").strip().lower()
                current_password_for_email = post.get("current_password_for_email") or ""
                age_raw = (post.get("age") or "").strip()
                gender = (post.get("gender") or "").strip()
                selected_interests = self._extract_interest_values()
                interests = ", ".join(selected_interests)

                age_value = 0
                if not full_name or not email:
                    error = "ФИО и email обязательны."
                else:
                    if age_raw:
                        try:
                            age_value = int(age_raw)
                        except ValueError:
                            error = "Возраст должен быть числом."
                        if age_value < 0 or age_value > 120:
                            error = "Возраст должен быть от 0 до 120."

                valid_genders = {"male", "female", "other", ""}
                if not error and gender not in valid_genders:
                    error = "Выбрано некорректное значение пола."

                if not error:
                    duplicate = (
                        request.env["res.users"]
                        .sudo()
                        .search_count([("login", "=", email), ("id", "!=", user.id)])
                    )
                    if duplicate:
                        error = "Пользователь с таким email уже существует."

                email_changed = email != (user.login or "").lower()
                if not error and email_changed:
                    if not current_password_for_email:
                        error = "Чтобы изменить email, введите текущий пароль."
                    else:
                        try:
                            uid = self._authenticate(user.login, current_password_for_email)
                        except AccessDenied:
                            uid = False
                        if uid != user.id:
                            error = "Текущий пароль указан неверно. Email не изменен."

                if not error:
                    user.write(
                        {
                            "name": full_name,
                            "login": email,
                            "email": email,
                        }
                    )
                    profile.write(
                        {
                            "name": full_name,
                            "em_age": age_value,
                            "em_gender": gender or False,
                            "em_interests": interests,
                        }
                    )
                    success = "Профиль успешно обновлен."

            elif action == "change_password":
                current_password = post.get("current_password") or ""
                new_password = post.get("new_password") or ""
                confirm_password = post.get("confirm_password") or ""

                if not current_password or not new_password or not confirm_password:
                    error = "Для смены пароля заполните все поля."
                elif new_password != confirm_password:
                    error = "Новый пароль и подтверждение не совпадают."
                elif len(new_password) < 8:
                    error = "Новый пароль должен содержать минимум 8 символов."
                else:
                    try:
                        uid = self._authenticate(user.login, current_password)
                    except AccessDenied:
                        uid = False
                    if uid != user.id:
                        error = "Текущий пароль указан неверно."
                    else:
                        user.write({"password": new_password})
                        success = "Пароль успешно изменен."

        events = user.personal_event_ids.sorted(key=lambda e: e.date_start or fields.Datetime.now())
        recommendation_source = request.env["eventmind.event"].sudo().search(
            self._upcoming_events_domain(),
            order="date_start asc",
        )
        recommendation_items = self._recommendations_for(user, recommendation_source)
        selected_interests = self._extract_partner_interest_values(profile)
        profile_form_values = {
            "full_name": profile.name or user.name or "",
            "email": user.login or user.email or "",
            "age": profile.em_age or "",
            "gender": profile.em_gender or "",
            "interests": selected_interests,
        }
        gender_labels = {
            "male": "Мужской",
            "female": "Женский",
            "other": "Другой",
        }
        return request.render(
            "eventmind.eventmind_cabinet_page",
            {
                "events": events,
                "recommendation_items": recommendation_items,
                "calendar_events_json": self._calendar_payload(events),
                "profile": profile,
                "profile_form_values": profile_form_values,
                "interest_tags": self.INTEREST_TAGS,
                "gender_label": gender_labels.get(profile.em_gender, "-"),
                "notification_items": self._notification_items_for(user),
                "error": error,
                "success": success,
            },
        )

    @http.route(
        "/eventmind/cabinet/calendar/add/<int:event_id>",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def add_event_to_cabinet(self, event_id, redirect=None, **kwargs):
        event = request.env["eventmind.event"].sudo().search(
            [("id", "=", event_id)] + self._upcoming_events_domain(),
            limit=1,
        )
        if event:
            event.write({"attendee_ids": [(4, request.env.uid)]})

        return request.redirect(redirect or "/eventmind/cabinet")

    @http.route(
        "/eventmind/cabinet/calendar/remove/<int:event_id>",
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def remove_event_from_cabinet(self, event_id, redirect=None, **kwargs):
        event = request.env["eventmind.event"].sudo().search([("id", "=", event_id)], limit=1)
        if event:
            event.write({"attendee_ids": [(3, request.env.uid)]})

        return request.redirect(redirect or "/eventmind/cabinet")
