import json

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

    @api.depends("attendee_ids")
    def _compute_attendee_count(self):
        for record in self:
            record.attendee_count = len(record.attendee_ids)

    @api.model
    def _normalize_datetime_value(self, value):
        if not value:
            return False
        if isinstance(value, str):
            return value.replace("T", " ")
        return value

    @api.model
    def import_timepad_json(self, file_path="/mnt/extra-addons/eventmind/data/timepad_full_events.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            events = json.load(f)

        for item in events:
            date_start = self._normalize_datetime_value(item.get("date_start"))
            date_end = self._normalize_datetime_value(item.get("date_end")) or date_start

            vals = {
                "name": item.get("name") or "Untitled event",
                "description": item.get("description") or "",
                "date_start": date_start or fields.Datetime.now(),
                "date_end": date_end or fields.Datetime.now(),
                "location": item.get("location") or "",
                "category": "other",
                "status": "planned",
                "source": "timepad",
                "source_url": item.get("url") or "",
                "external_id": item.get("url") or item.get("external_id") or "",
                "price": item.get("price") or "",
                "age_limit": item.get("age_limit") or "",
            }

            record = self.search([("external_id", "=", vals["external_id"])], limit=1)
            if record:
                record.write(vals)
            else:
                self.create(vals)

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
