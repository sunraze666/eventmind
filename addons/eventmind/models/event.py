from odoo import models, fields, api
from ..services.timepad_parser import fetch_timepad_events


class EventMindEvent(models.Model):
    _name = "eventmind.event"
    _description = "EventMind Event"
    _order = "date_start asc"

    name = fields.Char(string="Название", required=True)
    description = fields.Text(string="Описание")
    date_start = fields.Datetime(string="Дата и время", required=True)
    date_end = fields.Datetime(string="Дата окончания")
    location = fields.Char(string="Место")
    category = fields.Selection(
        [
            ("conference", "Conference"),
            ("meetup", "Meetup"),
            ("startup", "Startup Event"),
            ("education", "Education"),
            ("other", "Other"),
        ],
        string="Категория",
        default="other",
        required=True,
    )
    is_recommended = fields.Boolean(string="Рекомендовано", default=False)
    seats = fields.Integer(string="Количество мест")
    status = fields.Selection(
        [
            ("draft", "Черновик"),
            ("planned", "Запланировано"),
            ("done", "Завершено"),
            ("cancelled", "Отменено"),
        ],
        string="Статус",
        default="planned",
        required=True,
    )

    source = fields.Selection(
        [
            ("manual", "Manual"),
            ("timepad", "Timepad"),
        ],
        string="Источник",
        default="manual",
        required=True,
    )
    source_url = fields.Char(string="Ссылка на источник")
    external_id = fields.Char(string="Внешний ID", index=True)
    price = fields.Char(string="Цена")
    age_limit = fields.Char(string="Возрастное ограничение")

    _sql_constraints = [
        ("eventmind_event_external_id_uniq", "unique(external_id)", "External ID must be unique."),
    ]

    @api.model
    def import_timepad_events(self):
        events = fetch_timepad_events()

        for item in events:
            vals = {
                "name": item.get("name") or "Без названия",
                "description": item.get("description") or "",
                "date_start": item.get("date_start") or fields.Datetime.now(),
                "date_end": item.get("date_end") or item.get("date_start") or fields.Datetime.now(),
                "location": item.get("location") or "",
                "category": "other",
                "status": "planned",
                "source": "timepad",
                "source_url": item.get("url") or "",
                "external_id": item.get("external_id") or "",
                "price": item.get("price") or "",
                "age_limit": item.get("age_limit") or "",
            }

            record = self.search([("external_id", "=", vals["external_id"])], limit=1)
            if record:
                record.write(vals)
            else:
                self.create(vals)

        return True