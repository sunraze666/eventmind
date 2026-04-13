{
    "name": "EventMind",
    "version": "1.0",
    "summary": "Smart event assistant",
    "category": "Productivity",
    "depends": ["base", "web", "website"],
    "data": [
        "security/ir.model.access.csv",
        "views/event_views.xml",
        "views/menu.xml",
        "templates/eventmind_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "eventmind/static/src/css/eventmind.css",
            "eventmind/static/src/js/eventmind.js",
        ],
        "web.assets_frontend": [
            "eventmind/static/src/css/eventmind.css",
        ],
    },
    "installable": True,
    "application": True,
    "license": "LGPL-3",
}