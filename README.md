# EventMind

Odoo addon for the EventMind event assistant.

## Database

The project is configured to use a Supabase PostgreSQL database through
`odoo.local.conf`. This file is ignored by git because it contains local
credentials.

If you need to recreate it, copy `odoo.conf.example` to `odoo.local.conf` and
fill in `db_password`.

## Run

From your Odoo installation directory, run:

```powershell
python odoo-bin -c C:\Users\User\Desktop\eventmind\odoo.local.conf -d postgres
```

Then install or upgrade the module named `eventmind` from Odoo Apps.

If Odoo cannot find standard modules such as `base`, add your Odoo core addons
directory to `addons_path` before `C:\Users\User\Desktop\eventmind\addons`.
