import calendar
from collections import defaultdict
from datetime import date, timedelta

from odoo import fields, http
from odoo.http import request


class EventMindController(http.Controller):
    _MONTH_NAMES = [
        "??????",
        "???????",
        "????",
        "??????",
        "???",
        "????",
        "????",
        "??????",
        "????????",
        "???????",
        "??????",
        "???????",
    ]
    _WEEKDAY_NAMES = ["??", "??", "??", "??", "??", "??", "??"]

    @classmethod
    def _build_year_calendar_data(cls, events, year):
        first_day = date(year, 1, 1)
        last_day = date(year, 12, 31)
        event_days = defaultdict(int)

        for event in events:
            start_dt = fields.Datetime.to_datetime(event.date_start)
            end_dt = fields.Datetime.to_datetime(event.date_end or event.date_start)
            if not start_dt:
                continue

            start_day = start_dt.date()
            end_day = (end_dt or start_dt).date()
            if end_day < start_day:
                end_day = start_day

            clipped_start = max(start_day, first_day)
            clipped_end = min(end_day, last_day)
            if clipped_start > clipped_end:
                continue

            cursor = clipped_start
            while cursor <= clipped_end:
                event_days[cursor.isoformat()] += 1
                cursor += timedelta(days=1)

        calendar_builder = calendar.Calendar(firstweekday=0)
        today = fields.Date.context_today(request.env.user)
        months = []

        for month in range(1, 13):
            weeks = []
            for week in calendar_builder.monthdayscalendar(year, month):
                cells = []
                for day in week:
                    if not day:
                        cells.append(None)
                        continue

                    current_day = date(year, month, day)
                    day_key = current_day.isoformat()
                    cells.append(
                        {
                            "day": day,
                            "event_count": event_days.get(day_key, 0),
                            "is_today": current_day == today,
                        }
                    )
                weeks.append(cells)

            months.append(
                {
                    "name": cls._MONTH_NAMES[month - 1],
                    "year": year,
                    "weeks": weeks,
                }
            )

        return {
            "year": year,
            "weekday_names": cls._WEEKDAY_NAMES,
            "months": months,
        }

    @http.route("/eventmind/events", type="http", auth="public", website=True)
    def eventmind_events(self, **kwargs):
        events = request.env["eventmind.event"].sudo().search(
            [("status", "!=", "cancelled")],
            order="date_start asc"
        )

        current_year = fields.Date.context_today(request.env.user).year
        year_param = kwargs.get("year")
        try:
            selected_year = int(year_param) if year_param else current_year
        except (TypeError, ValueError):
            selected_year = current_year

        if selected_year < 1900 or selected_year > 2100:
            selected_year = current_year

        calendar_data = self._build_year_calendar_data(events, selected_year)

        return request.render("eventmind.eventmind_events_page", {
            "events": events,
            "calendar_data": calendar_data,
            "prev_year": selected_year - 1,
            "next_year": selected_year + 1,
            "current_year": current_year,
        })
