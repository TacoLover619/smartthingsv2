"""Constants used by the SmartThings component and platforms."""

from datetime import timedelta
import re

from homeassistant.const import Platform

DOMAIN = "smartthings"

# OAuth and App Configuration
APP_OAUTH_CLIENT_NAME = "Home Assistant"
APP_OAUTH_SCOPES = ["r:devices:*"]
APP_NAME_PREFIX = "homeassistant."

# Configuration Keys
CONF_APP_ID = "app_id"
CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_INSTALLED_APP_ID = "installed_app_id"
CONF_INSTANCE_ID = "instance_id"
CONF_LOCATION_ID = "location_id"
CONF_REFRESH_TOKEN = "refresh_token"

# Data Keys
DATA_MANAGER = "manager"
DATA_BROKERS = "brokers"
EVENT_BUTTON = "smartthings.button"

# Signals
SIGNAL_SMARTTHINGS_UPDATE = "smartthings_update"
SIGNAL_SMARTAPP_PREFIX = "smartthings_smartap_"

# Storage Keys
SETTINGS_INSTANCE_ID = "hassInstanceId"
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

# Platform Support
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Logging and Debugging
IGNORED_CAPABILITIES = [
    "execute",
    "healthCheck",
    "ocf",
]
SUBSCRIPTION_WARNING_LIMIT = 40

TOKEN_REFRESH_INTERVAL = timedelta(days=14)

# Regular Expressions
VAL_UID = "^(?:([0-9a-fA-F]{32})|([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}))$"
VAL_UID_MATCHER = re.compile(VAL_UID)

# Logging Enhancements
DEBUGGING_TAG = "[SmartThings Debug]"
