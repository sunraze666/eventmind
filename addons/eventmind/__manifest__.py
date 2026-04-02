{
    "name": "EventMind",
    "version": "1.0",
    "summary": "Smart event assistant",
    "category": "Productivity",
    "depends": ["base", "web"],
    "data": [
        "views/event_views.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "eventmind/static/src/css/eventmind.css",
            "eventmind/static/src/js/eventmind.js",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}