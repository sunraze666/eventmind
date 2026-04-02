from odoo import models, fields


class EventMindEvent(models.Model):
    _name = "eventmind.event"
    _description = "EventMind Event"
    _order = "date_start asc"

    name = fields.Char(string="Название", required=True)
    description = fields.Text(string="Описание")
    date_start = fields.Datetime(string="Дата и время")
    location = fields.Char(string="Место")
    category = fields.Selection(
        [
            ("conference", "Conference"),
            ("meetup", "Meetup"),
            ("startup", "Startup Event"),
            ("education", "Education"),
        ],
        string="Категория",
    )
    is_recommended = fields.Boolean(string="Рекомендовано", default=False)