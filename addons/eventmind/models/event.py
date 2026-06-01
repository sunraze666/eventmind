import json
from pathlib import Path

from odoo import api, fields, models


class EventMindEvent(models.Model):
    _name = "eventmind.event"
    _description = "EventMind Event"
    _order = "date_start asc"

    name = fields.Char(string="Name", required=True)
    description = fields.Text(string="Description")
    date_start = fields.Datetime(string="Start", required=True)
    date_end = fields.Datetime(string="End")
    location = fields.Char(string="Location")
    category = fields.Selection(
        [
            ("conference", "Conference"),
            ("meetup", "Meetup"),
            ("startup", "Startup Event"),
            ("education", "Education"),
            ("other", "Other"),
        ],
        string="Category",
        default="other",
        required=True,
    )
    is_recommended = fields.Boolean(string="Recommended", default=False)
    seats = fields.Integer(string="Seats")
    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("planned", "Planned"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="planned",
        required=True,
    )

    source = fields.Selection(
        [
            ("manual", "Manual"),
            ("timepad", "Timepad"),
        ],
        string="Source",
        default="manual",
        required=True,
    )
    source_url = fields.Char(string="Source URL")
    external_id = fields.Char(string="External ID", index=True)
    price = fields.Char(string="Price")
    age_limit = fields.Char(string="Age Limit")
    attendee_ids = fields.Many2many(
        "res.users",
        "eventmind_event_user_rel",
        "event_id",
        "user_id",
        string="Users in personal calendar",
    )
    attendee_count = fields.Integer(string="Users Count", compute="_compute_attendee_count")

    _sql_constraints = [
        ("eventmind_event_external_id_uniq", "unique(external_id)", "External ID must be unique."),
    ]

    _MONTHS_GENITIVE_RU = {
        1: "\u044f\u043d\u0432\u0430\u0440\u044f",
        2: "\u0444\u0435\u0432\u0440\u0430\u043b\u044f",
        3: "\u043c\u0430\u0440\u0442\u0430",
        4: "\u0430\u043f\u0440\u0435\u043b\u044f",
        5: "\u043c\u0430\u044f",
        6: "\u0438\u044e\u043d\u044f",
        7: "\u0438\u044e\u043b\u044f",
        8: "\u0430\u0432\u0433\u0443\u0441\u0442\u0430",
        9: "\u0441\u0435\u043d\u0442\u044f\u0431\u0440\u044f",
        10: "\u043e\u043a\u0442\u044f\u0431\u0440\u044f",
        11: "\u043d\u043e\u044f\u0431\u0440\u044f",
        12: "\u0434\u0435\u043a\u0430\u0431\u0440\u044f",
    }

    @api.depends("attendee_ids")
    def _compute_attendee_count(self):
        for record in self:
            record.attendee_count = len(record.attendee_ids)

    @api.model
    def _normalize_datetime_value(self, value):
        if not value:
            return False
        if isinstance(value, str):
            normalized = value.strip().replace("T", " ")
            if len(normalized) == 16:
                normalized = f"{normalized}:00"
            return normalized[:19]
        return value

    @api.model
    def _default_timepad_json_path(self):
        return Path(__file__).resolve().parents[1] / "data" / "timepad_full_events.json"

    def eventmind_display_datetime(self):
        self.ensure_one()
        start_dt = fields.Datetime.to_datetime(self.date_start)
        if not start_dt:
            return "-"

        start_dt = fields.Datetime.context_timestamp(self, start_dt)
        month = self._MONTHS_GENITIVE_RU.get(start_dt.month, "")
        return f"{start_dt.day} {month} {start_dt.year}, {start_dt:%H:%M}"

    @api.model
    def import_timepad_json(self, file_path=None, cancel_stale=True):
        file_path = file_path or self._default_timepad_json_path()
        with open(file_path, "r", encoding="utf-8") as f:
            events = json.load(f)

        imported_external_ids = set()

        for item in events:
            date_start = self._normalize_datetime_value(item.get("date_start"))
            if not date_start:
                continue

            date_end = self._normalize_datetime_value(item.get("date_end")) or date_start
            external_id = item.get("url") or item.get("external_id") or ""
            if not external_id:
                continue

            imported_external_ids.add(external_id)

            vals = {
                "name": item.get("name") or "Untitled event",
                "description": item.get("description") or "",
                "date_start": date_start,
                "date_end": date_end,
                "location": item.get("location") or "",
                "category": "other",
                "status": "planned",
                "source": "timepad",
                "source_url": item.get("url") or "",
                "external_id": external_id,
                "price": item.get("price") or "",
                "age_limit": item.get("age_limit") or "",
            }

            record = self.search([("external_id", "=", vals["external_id"])], limit=1)
            if record:
                record.write(vals)
            else:
                self.create(vals)

        if cancel_stale:
            stale_domain = [("source", "=", "timepad"), ("status", "!=", "cancelled")]
            if imported_external_ids:
                stale_domain.append(("external_id", "not in", list(imported_external_ids)))
            self.search(stale_domain).write({"status": "cancelled"})

        return True


class EventMindPartner(models.Model):
    _inherit = "res.partner"

    em_age = fields.Integer(string="Age")
    em_gender = fields.Selection(
        [
            ("male", "Male"),
            ("female", "Female"),
            ("other", "Other"),
        ],
        string="Gender",
    )
    em_interests = fields.Text(string="Interests")


class EventMindUsers(models.Model):
    _inherit = "res.users"

    personal_event_ids = fields.Many2many(
        "eventmind.event",
        "eventmind_event_user_rel",
        "user_id",
        "event_id",
        string="My calendar events",
    )
