from odoo import models, fields


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
        ],
        string="Категория",
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
        default="draft",
        required=True,
    )