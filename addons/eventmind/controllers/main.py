import json

from odoo import fields, http
from odoo.exceptions import AccessDenied
from odoo.http import request


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

    @http.route("/eventmind/events", type="http", auth="public", website=True)
    def eventmind_events(self, **kwargs):
        events = request.env["eventmind.event"].sudo().search(
            [("status", "!=", "cancelled")],
            order="date_start asc",
        )

        user_event_ids = []
        if not request.env.user._is_public():
            user_event_ids = request.env.user.sudo().personal_event_ids.ids

        return request.render(
            "eventmind.eventmind_events_page",
            {
                "events": events,
                "user_event_ids": user_event_ids,
                "calendar_events_json": self._calendar_payload(events),
            },
        )

    @http.route("/eventmind/login", type="http", auth="public", website=True, methods=["GET", "POST"])
    def eventmind_login(self, **post):
        if request.httprequest.method == "GET":
            return request.render("eventmind.eventmind_login_page", {"error": ""})

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
            },
        )

    @http.route("/eventmind/signup", type="http", auth="public", website=True, methods=["GET", "POST"])
    def eventmind_signup(self, **post):
        if request.httprequest.method == "GET":
            return request.render(
                "eventmind.eventmind_signup_page",
                {"error": "", "values": {}, "interest_tags": self.INTEREST_TAGS},
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
                "calendar_events_json": self._calendar_payload(events),
                "profile": profile,
                "profile_form_values": profile_form_values,
                "interest_tags": self.INTEREST_TAGS,
                "gender_label": gender_labels.get(profile.em_gender, "-"),
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
            [("id", "=", event_id), ("status", "!=", "cancelled")],
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
