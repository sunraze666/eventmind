import json

from odoo import fields, http
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

    @http.route("/eventmind/events", type="http", auth="public", website=True)
    def eventmind_events(self, **kwargs):
        events = request.env["eventmind.event"].sudo().search(
            [("status", "!=", "cancelled")],
            order="date_start asc",
        )

        calendar_events = []
        for event in events:
            serialized = self._serialize_event_for_calendar(event)
            if serialized:
                calendar_events.append(serialized)

        return request.render(
            "eventmind.eventmind_events_page",
            {
                "events": events,
                "calendar_events_json": json.dumps(calendar_events, ensure_ascii=False),
            },
        )
