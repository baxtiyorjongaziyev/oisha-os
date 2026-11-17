"""Card-sent -> payment watcher.

Detects company card numbers sent by sales managers in Telegram, matches them
against Airtable ``Tranzaksiyalar`` income rows and reminds the manager in
their sales-group topic when no payment arrives within N days.
"""
