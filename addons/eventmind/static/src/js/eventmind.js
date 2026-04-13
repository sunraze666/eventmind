/** @odoo-module **/

const VIEW_YEAR = "year";
const VIEW_MONTH = "month";
const VIEW_WEEK = "week";
const VIEW_DAY = "day";
const DENSITY_TONE = "tone";
const DENSITY_COUNT = "count";
const VIEWS = [VIEW_YEAR, VIEW_MONTH, VIEW_WEEK, VIEW_DAY];
const DENSITIES = [DENSITY_TONE, DENSITY_COUNT];
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

function truncateText(value, maxLength) {
    const text = String(value || "");
    if (text.length <= maxLength) {
        return text;
    }
    return `${text.slice(0, maxLength - 1)}...`;
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

function formatTime(date) {
    return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
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

function getMaxEventsPerDay(eventsMap) {
    let max = 0;
    for (const events of eventsMap.values()) {
        if (events.length > max) {
            max = events.length;
        }
    }
    return max;
}

function getIntensityLevel(count, maxCount) {
    if (!count || !maxCount) {
        return 0;
    }
    if (maxCount <= 1) {
        return 5;
    }
    const ratio = count / maxCount;
    if (ratio <= 0.2) {
        return 1;
    }
    if (ratio <= 0.4) {
        return 2;
    }
    if (ratio <= 0.6) {
        return 3;
    }
    if (ratio <= 0.8) {
        return 4;
    }
    return 5;
}

function createEventChip(event) {
    const title = escapeHtml(truncateText(event.title, 22));
    const time = escapeHtml(formatTime(event.start));
    const content = `<span class="em-event-chip-time">${time}</span><span class="em-event-chip-title">${title}</span>`;
    const safeUrl = sanitizeUrl(event.url);
    if (safeUrl) {
        return `<a class="em-event-chip" href="${safeUrl}" target="_blank" rel="noopener noreferrer">${content}</a>`;
    }
    return `<span class="em-event-chip em-event-chip-muted">${content}</span>`;
}

function createEventCard(event) {
    const title = escapeHtml(truncateText(event.title, 72));
    const location = event.location ? escapeHtml(truncateText(event.location, 44)) : "";
    const time = escapeHtml(formatTime(event.start));
    const safeUrl = sanitizeUrl(event.url);
    return `<article class="em-event-card">
        <div class="em-event-card-head">
            <span class="em-event-time">${time}</span>
            <span class="em-event-title">${title}</span>
        </div>
        ${location ? `<div class="em-event-meta">${location}</div>` : ""}
        ${safeUrl ? `<a class="em-event-link" href="${safeUrl}" target="_blank" rel="noopener noreferrer">Подробнее</a>` : ""}
    </article>`;
}

function renderWeekHeader() {
    return `<div class="em-week-header">${WEEKDAYS_RU.map((day) => `<span>${day}</span>`).join("")}</div>`;
}

function renderMonthGrid(year, monthIndex, eventsMap, options = {}) {
    const today = dateKey(new Date());
    const firstDay = new Date(year, monthIndex, 1);
    const offset = (firstDay.getDay() + 6) % 7;
    const totalDays = daysInMonth(year, monthIndex);
    const showTone = options.densityMode === DENSITY_TONE;
    const showCount = options.densityMode === DENSITY_COUNT;
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
        if (events.length && showTone) {
            const intensity = getIntensityLevel(events.length, options.maxDailyCount || 1);
            if (intensity) {
                classes.push(`em-density-level-${intensity}`);
            }
        }

        let eventsHtml = "";
        if (options.compact) {
            eventsHtml = showCount && events.length ? `<span class="em-day-badge">${events.length}</span>` : "";
        } else if (events.length) {
            const chips = events.slice(0, 2).map(createEventChip).join("");
            const more = events.length > 2 ? `<span class="em-day-more">+${events.length - 2}</span>` : "";
            const badge = showCount ? `<span class="em-day-count-inline">${events.length}</span>` : "";
            eventsHtml = `<div class="em-day-events">${chips}${more}${badge}</div>`;
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

function renderYearView(cursor, eventsMap, options) {
    const year = cursor.getFullYear();
    const months = MONTHS_RU.map((monthName, monthIndex) => {
        return `<article class="em-month-card">
            <h3 class="em-month-title">${monthName} ${year}</h3>
            ${renderWeekHeader()}
            ${renderMonthGrid(year, monthIndex, eventsMap, {
                compact: true,
                densityMode: options.densityMode,
                maxDailyCount: options.maxDailyCount,
            })}
        </article>`;
    }).join("");
    return `<div class="em-year-grid">${months}</div>`;
}

function renderMonthView(cursor, eventsMap, options) {
    const year = cursor.getFullYear();
    const monthIndex = cursor.getMonth();
    return `${renderWeekHeader()}${renderMonthGrid(year, monthIndex, eventsMap, {
        compact: false,
        densityMode: options.densityMode,
        maxDailyCount: options.maxDailyCount,
    })}`;
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
            <div class="em-week-day-body">${events.length ? events.map(createEventCard).join("") : '<span class="em-empty-note">Нет событий</span>'}</div>
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
    return `<div class="em-day-list">${events.map(createEventCard).join("")}</div>`;
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

function renderCalendar(root, state, eventsMap, stats) {
    const body = root.querySelector("[data-em-calendar-body]");
    const label = root.querySelector("[data-em-current-label]");
    if (!body || !label) {
        return;
    }

    let markup = "";
    if (state.view === VIEW_YEAR) {
        markup = renderYearView(state.cursor, eventsMap, {
            densityMode: state.densityMode,
            maxDailyCount: stats.maxDailyCount,
        });
    } else if (state.view === VIEW_MONTH) {
        markup = renderMonthView(state.cursor, eventsMap, {
            densityMode: state.densityMode,
            maxDailyCount: stats.maxDailyCount,
        });
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
    root.querySelectorAll("[data-em-density]").forEach((button) => {
        const isActive = button.dataset.emDensity === state.densityMode;
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
            renderCalendar(root, state, eventsMap, stats);
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
    const stats = {
        maxDailyCount: getMaxEventsPerDay(eventsMap),
    };
    const state = {
        view: VIEW_MONTH,
        densityMode: DENSITY_TONE,
        cursor: startOfDay(new Date()),
    };

    root.querySelectorAll("[data-em-view]").forEach((button) => {
        button.addEventListener("click", () => {
            const requestedView = button.dataset.emView;
            if (!VIEWS.includes(requestedView)) {
                return;
            }
            state.view = requestedView;
            renderCalendar(root, state, eventsMap, stats);
        });
    });
    root.querySelectorAll("[data-em-density]").forEach((button) => {
        button.addEventListener("click", () => {
            const requestedDensity = button.dataset.emDensity;
            if (!DENSITIES.includes(requestedDensity)) {
                return;
            }
            state.densityMode = requestedDensity;
            renderCalendar(root, state, eventsMap, stats);
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
            renderCalendar(root, state, eventsMap, stats);
        });
    });

    renderCalendar(root, state, eventsMap, stats);
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootEventMindCalendar);
} else {
    bootEventMindCalendar();
}
