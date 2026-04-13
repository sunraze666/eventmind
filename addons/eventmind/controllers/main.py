from odoo import http
from odoo.http import request


class EventMindController(http.Controller):

    @http.route("/eventmind/events", type="http", auth="public", website=True)
    def eventmind_events(self, **kwargs):
        events = request.env["eventmind.event"].sudo().search(
            [("status", "!=", "cancelled")],
            order="date_start asc"
        )
        return request.render("eventmind.eventmind_events_page", {
            "events": events
        })