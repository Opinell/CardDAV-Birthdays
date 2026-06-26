from datetime import timedelta

DOMAIN = "carddav_birthdays"

CONF_SERVER_URL = "server_url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_UPCOMING_DAYS = "upcoming_days"

DEFAULT_UPCOMING_DAYS = 30

SCAN_INTERVAL = timedelta(hours=1)
CARDDAV_REFETCH_INTERVAL = timedelta(hours=24)
