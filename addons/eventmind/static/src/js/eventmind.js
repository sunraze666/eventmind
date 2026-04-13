/** @odoo-module **/

const VIEW_YEAR = "year";
const VIEW_MONTH = "month";
const VIEW_WEEK = "week";
const VIEW_DAY = "day";
const VIEWS = [VIEW_YEAR, VIEW_MONTH, VIEW_WEEK, VIEW_DAY];
const WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
const MONTHS_RU = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
];

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function sanitizeUrl(value) {
    if (!value) {
        return "";
    }
    const trimmed = String(value).trim();
    if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
        return trimmed;
    }
    return "";
}

function parseDate(value) {
    if (!value) {
        return null;
    }
    const normalized = String(value).replace(" ", "T");
    const date = new Date(normalized);
    return Number.isNaN(date.getTime()) ? null : date;
}

function startOfDay(date) {
    return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function startOfWeek(date) {
    const dayIndex = (date.getDay() + 6) % 7;
    return addDays(startOfDay(date), -dayIndex);
}

function addDays(date, days) {
    const result = new Date(date);
    result.setDate(result.getDate() + days);
    return result;
}

function daysInMonth(year, monthIndex) {
    return new Date(year, monthIndex + 1, 0).getDate();
}

function dateKey(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, "0");
    const d = String(date.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
}

function formatShortDate(date) {
    return `${String(date.getDate()).padStart(2, "0")}.${String(date.getMonth() + 1).padStart(2, "0")}.${date.getFullYear()}`;
}

function getSpanDays(event) {
    const start = startOfDay(event.start);
    const end = startOfDay(event.end || event.start);
    const days = [];
    let cursor = start;
    while (cursor <= end) {
        days.push(dateKey(cursor));
        cursor = addDays(cursor, 1);
    }
    return days;
}

function prepareEvents(rawEvents) {
    return rawEvents
        .map((event) => {
            const start = parseDate(event.start);
            const end = parseDate(event.end || event.start) || start;
            if (!start) {
                return null;
            }
            return {
                id: event.id,
                title: event.title || "Без названия",
                location: event.location || "",
                url: event.url || "",
                start,
                end: end >= start ? end : start,
            };
        })
        .filter(Boolean)
        .sort((a, b) => a.start - b.start);
}

function createEventsMap(events) {
    const map = new Map();
    for (const event of events) {
        const keys = getSpanDays(event);
        for (const key of keys) {
            if (!map.has(key)) {
                map.set(key, []);
            }
            map.get(key).push(event);
        }
    }
    return map;
}

function createEventMarkup(event) {
    const labelParts = [event.title];
    if (event.location) {
        labelParts.push(event.location);
    }
    const label = escapeHtml(labelParts.join(" - "));
    const safeUrl = sanitizeUrl(event.url);
    if (safeUrl) {
        return `<a class="em-event-pill" href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`;
    }
    return `<span class="em-event-pill">${label}</span>`;
}

function renderWeekHeader() {
    return `<div class="em-week-header">${WEEKDAYS_RU.map((day) => `<span>${day}</span>`).join("")}</div>`;
}

function renderMonthGrid(year, monthIndex, eventsMap, options = {}) {
    const today = dateKey(new Date());
    const firstDay = new Date(year, monthIndex, 1);
    const offset = (firstDay.getDay() + 6) % 7;
    const totalDays = daysInMonth(year, monthIndex);
    const cells = [];

    for (let i = 0; i < offset; i++) {
        cells.push('<div class="em-day-cell em-day-empty"></div>');
    }

    for (let day = 1; day <= totalDays; day++) {
        const current = new Date(year, monthIndex, day);
        const key = dateKey(current);
        const events = eventsMap.get(key) || [];
        const classes = ["em-day-cell"];
        if (key === today) {
            classes.push("em-day-today");
        }
        if (events.length) {
            classes.push("em-day-with-events");
        }

        let eventsHtml = "";
        if (options.compact) {
            eventsHtml = events.length ? `<span class="em-day-badge">${events.length}</span>` : "";
        } else if (events.length) {
            eventsHtml = `<div class="em-day-events">${events.slice(0, 2).map(createEventMarkup).join("")}${events.length > 2 ? `<span class="em-day-more">+${events.length - 2}</span>` : ""}</div>`;
        }

        cells.push(
            `<div class="${classes.join(" ")}" data-em-date="${key}">
                <span class="em-day-number">${day}</span>
                ${eventsHtml}
            </div>`
        );
    }

    return `<div class="em-month-grid">${cells.join("")}</div>`;
}

function renderYearView(cursor, eventsMap) {
    const year = cursor.getFullYear();
    const months = MONTHS_RU.map((monthName, monthIndex) => {
        return `<article class="em-month-card">
            <h3 class="em-month-title">${monthName} ${year}</h3>
            ${renderWeekHeader()}
            ${renderMonthGrid(year, monthIndex, eventsMap, { compact: true })}
        </article>`;
    }).join("");
    return `<div class="em-year-grid">${months}</div>`;
}

function renderMonthView(cursor, eventsMap) {
    const year = cursor.getFullYear();
    const monthIndex = cursor.getMonth();
    return `${renderWeekHeader()}${renderMonthGrid(year, monthIndex, eventsMap, { compact: false })}`;
}

function renderWeekView(cursor, eventsMap) {
    const weekStart = startOfWeek(cursor);
    const columns = [];
    for (let i = 0; i < 7; i++) {
        const current = addDays(weekStart, i);
        const key = dateKey(current);
        const events = eventsMap.get(key) || [];
        columns.push(`<div class="em-week-day">
            <div class="em-week-day-head">${WEEKDAYS_RU[i]}, ${formatShortDate(current)}</div>
            <div class="em-week-day-body">${events.length ? events.map(createEventMarkup).join("") : '<span class="em-empty-note">Нет событий</span>'}</div>
        </div>`);
    }
    return `<div class="em-week-grid">${columns.join("")}</div>`;
}

function renderDayView(cursor, eventsMap) {
    const key = dateKey(cursor);
    const events = eventsMap.get(key) || [];
    if (!events.length) {
        return `<div class="em-day-list"><span class="em-empty-note">На ${formatShortDate(cursor)} событий нет.</span></div>`;
    }
    return `<div class="em-day-list">${events.map(createEventMarkup).join("")}</div>`;
}

function getTitle(view, cursor) {
    if (view === VIEW_YEAR) {
        return String(cursor.getFullYear());
    }
    if (view === VIEW_MONTH) {
        return `${MONTHS_RU[cursor.getMonth()]} ${cursor.getFullYear()}`;
    }
    if (view === VIEW_WEEK) {
        const start = startOfWeek(cursor);
        const end = addDays(start, 6);
        return `${formatShortDate(start)} - ${formatShortDate(end)}`;
    }
    return formatShortDate(cursor);
}

function moveCursor(cursor, view, direction) {
    const next = new Date(cursor);
    if (view === VIEW_YEAR) {
        next.setFullYear(next.getFullYear() + direction);
    } else if (view === VIEW_MONTH) {
        next.setMonth(next.getMonth() + direction);
    } else {
        next.setDate(next.getDate() + (view === VIEW_WEEK ? 7 * direction : direction));
    }
    return next;
}

function renderCalendar(root, state, eventsMap) {
    const body = root.querySelector("[data-em-calendar-body]");
    const label = root.querySelector("[data-em-current-label]");
    if (!body || !label) {
        return;
    }

    let markup = "";
    if (state.view === VIEW_YEAR) {
        markup = renderYearView(state.cursor, eventsMap);
    } else if (state.view === VIEW_MONTH) {
        markup = renderMonthView(state.cursor, eventsMap);
    } else if (state.view === VIEW_WEEK) {
        markup = renderWeekView(state.cursor, eventsMap);
    } else {
        markup = renderDayView(state.cursor, eventsMap);
    }

    body.innerHTML = markup;
    label.textContent = getTitle(state.view, state.cursor);

    root.querySelectorAll("[data-em-view]").forEach((button) => {
        const isActive = button.dataset.emView === state.view;
        button.classList.toggle("btn-primary", isActive);
        button.classList.toggle("btn-outline-secondary", !isActive);
    });

    body.querySelectorAll("[data-em-date]").forEach((dayCell) => {
        dayCell.addEventListener("click", () => {
            const value = dayCell.dataset.emDate;
            if (!value) {
                return;
            }
            const target = parseDate(`${value}T00:00:00`);
            if (!target) {
                return;
            }
            state.cursor = target;
            state.view = VIEW_DAY;
            renderCalendar(root, state, eventsMap);
        });
    });
}

function bootEventMindCalendar() {
    const root = document.querySelector("[data-em-calendar]");
    if (!root) {
        return;
    }

    const rawDataEl = document.getElementById("em-calendar-events");
    let rawEvents = [];
    if (rawDataEl) {
        try {
            rawEvents = JSON.parse(rawDataEl.textContent || "[]");
        } catch (error) {
            rawEvents = [];
        }
    }

    const events = prepareEvents(rawEvents);
    const eventsMap = createEventsMap(events);
    const state = {
        view: VIEW_MONTH,
        cursor: startOfDay(new Date()),
    };

    root.querySelectorAll("[data-em-view]").forEach((button) => {
        button.addEventListener("click", () => {
            const requestedView = button.dataset.emView;
            if (!VIEWS.includes(requestedView)) {
                return;
            }
            state.view = requestedView;
            renderCalendar(root, state, eventsMap);
        });
    });

    root.querySelectorAll("[data-em-nav]").forEach((button) => {
        button.addEventListener("click", () => {
            const action = button.dataset.emNav;
            if (action === "today") {
                state.cursor = startOfDay(new Date());
            } else if (action === "prev") {
                state.cursor = moveCursor(state.cursor, state.view, -1);
            } else if (action === "next") {
                state.cursor = moveCursor(state.cursor, state.view, 1);
            }
            renderCalendar(root, state, eventsMap);
        });
    });

    renderCalendar(root, state, eventsMap);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootEventMindCalendar);
} else {
    bootEventMindCalendar();
}
