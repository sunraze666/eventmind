import json

from odoo import fields, http
from odoo.exceptions import AccessDenied
from odoo.http import request


class EventMindController(http.Controller):
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
            error = "Fill in email and password."
        else:
            try:
                uid = self._authenticate(login, password)
                if uid:
                    return request.redirect("/eventmind/cabinet")
                error = "Invalid email or password."
            except AccessDenied:
                error = "Invalid email or password."

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
            return request.render("eventmind.eventmind_signup_page", {"error": "", "values": {}})

        full_name = (post.get("full_name") or "").strip()
        login = (post.get("login") or "").strip().lower()
        password = post.get("password") or ""
        password_confirm = post.get("password_confirm") or ""
        age_raw = (post.get("age") or "").strip()
        gender = (post.get("gender") or "").strip()
        interests = (post.get("interests") or "").strip()

        values = {
            "full_name": full_name,
            "login": login,
            "age": age_raw,
            "gender": gender,
            "interests": interests,
        }

        error = ""
        age = 0
        if not full_name or not login or not password:
            error = "Full name, email, and password are required."
        elif password != password_confirm:
            error = "Passwords do not match."
        else:
            if age_raw:
                try:
                    age = int(age_raw)
                except ValueError:
                    error = "Age must be a number."
                if age < 0 or age > 120:
                    error = "Age must be between 0 and 120."

        users = request.env["res.users"].sudo()
        if not error and users.search_count([("login", "=", login)]):
            error = "A user with this email already exists."

        if error:
            return request.render(
                "eventmind.eventmind_signup_page",
                {
                    "error": error,
                    "values": values,
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

        self._authenticate(login, password)
        return request.redirect("/eventmind/cabinet")

    @http.route("/eventmind/cabinet", type="http", auth="user", website=True)
    def eventmind_cabinet(self, **kwargs):
        user = request.env.user
        events = user.sudo().personal_event_ids.sorted(key=lambda e: e.date_start or fields.Datetime.now())
        gender_labels = {
            "male": "Male",
            "female": "Female",
            "other": "Other",
        }
        return request.render(
            "eventmind.eventmind_cabinet_page",
            {
                "events": events,
                "calendar_events_json": self._calendar_payload(events),
                "profile": user.partner_id,
                "gender_label": gender_labels.get(user.partner_id.em_gender, "-"),
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
