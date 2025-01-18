"""Config flow to configure SmartThings."""

from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError
from pysmartthings import APIResponseError, AppOAuth, SmartThings
from pysmartthings.installedapp import format_install_url
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    APP_OAUTH_CLIENT_NAME,
    APP_OAUTH_SCOPES,
    CONF_APP_ID,
    CONF_INSTALLED_APP_ID,
    CONF_LOCATION_ID,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    VAL_UID_MATCHER,
)
from .smartapp import (
    create_app,
    find_app,
    format_unique_id,
    get_webhook_url,
    setup_smartapp,
    setup_smartapp_endpoint,
    update_app,
    validate_webhook_requirements,
)

_LOGGER = logging.getLogger(__name__)


class SmartThingsFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle configuration of SmartThings integrations."""

    VERSION = 2

    api: SmartThings
    app_id: str
    location_id: str

    def __init__(self) -> None:
        """Create a new instance of the flow handler."""
        self.access_token: str | None = None
        self.oauth_client_secret = None
        self.oauth_client_id = None
        self.installed_app_id = None
        self.refresh_token = None
        self.endpoints_initialized = False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and confirm webhook setup."""
        if not self.endpoints_initialized:
            self.endpoints_initialized = True
            await setup_smartapp_endpoint(
                self.hass, len(self._async_current_entries()) == 0
            )
        webhook_url = get_webhook_url(self.hass)

        # Abort if the webhook is invalid
        if not validate_webhook_requirements(self.hass):
            _LOGGER.error(
                "Invalid webhook URL: %s. Ensure it's reachable from the internet.",
                webhook_url,
            )
            return self.async_abort(reason="invalid_webhook_url")

        if user_input is None:
            _LOGGER.debug("Displaying webhook confirmation form.")
            return self.async_show_form(
                step_id="user",
                description_placeholders={"webhook_url": webhook_url},
            )

        _LOGGER.debug("Proceeding to PAT entry step.")
        return await self.async_step_pat()

    async def async_step_pat(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Get the Personal Access Token and validate it."""
        errors: dict[str, str] = {}
        if user_input is None or CONF_ACCESS_TOKEN not in user_input:
            _LOGGER.debug("Displaying PAT entry form.")
            return self._show_step_pat(errors)

        self.access_token = user_input[CONF_ACCESS_TOKEN]

        # Ensure token is a UUID
        if not VAL_UID_MATCHER.match(self.access_token):
            errors[CONF_ACCESS_TOKEN] = "token_invalid_format"
            _LOGGER.error("Invalid token format provided.")
            return self._show_step_pat(errors)

        _LOGGER.debug("Attempting to validate token with SmartThings API.")
        self.api = SmartThings(async_get_clientsession(self.hass), self.access_token)
        try:
            app = await find_app(self.hass, self.api)
            if app:
                await app.refresh()
                await update_app(self.hass, app)
                self.app_id = app.app_id
            else:
                app, client = await create_app(self.hass, self.api)
                self.oauth_client_id = client.client_id
                self.oauth_client_secret = client.client_secret
                self.app_id = app.app_id

            setup_smartapp(self.hass, app)

        except (APIResponseError, ClientResponseError) as ex:
            _LOGGER.error("Error validating token or setting up SmartApp: %s", ex)
            errors["base"] = "app_setup_error"
            return self._show_step_pat(errors)

        _LOGGER.debug("Token validated. Proceeding to location selection.")
        return await self.async_step_select_location()

    async def async_step_select_location(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Ask user to select the location to set up."""
        if user_input is None or CONF_LOCATION_ID not in user_input:
            _LOGGER.debug("Fetching available SmartThings locations.")
            locations = await self.api.locations()
            locations_options = {
                location.location_id: location.name
                for location in locations
            }
            if not locations_options:
                _LOGGER.error("No available locations found.")
                return self.async_abort(reason="no_available_locations")

            return self.async_show_form(
                step_id="select_location",
                data_schema=vol.Schema(
                    {vol.Required(CONF_LOCATION_ID): vol.In(locations_options)}
                ),
            )

        self.location_id = user_input[CONF_LOCATION_ID]
        _LOGGER.debug("Location selected: %s", self.location_id)
        return await self.async_step_authorize()

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Wait for the user to authorize the app installation."""
        if user_input:
            self.installed_app_id = user_input.get(CONF_INSTALLED_APP_ID)
            self.refresh_token = user_input.get(CONF_REFRESH_TOKEN)
            _LOGGER.debug("Authorization completed. Finalizing setup.")
            return self.async_create_entry(
                title="SmartThings",
                data={
                    CONF_ACCESS_TOKEN: self.access_token,
                    CONF_REFRESH_TOKEN: self.refresh_token,
                    CONF_CLIENT_ID: self.oauth_client_id,
                    CONF_CLIENT_SECRET: self.oauth_client_secret,
                    CONF_LOCATION_ID: self.location_id,
                    CONF_APP_ID: self.app_id,
                    CONF_INSTALLED_APP_ID: self.installed_app_id,
                },
            )

        _LOGGER.debug("Prompting user for app authorization.")
        url = format_install_url(self.app_id, self.location_id)
        return self.async_external_step(step_id="authorize", url=url)

    def _show_step_pat(self, errors):
        _LOGGER.debug("Returning to PAT input form with errors: %s", errors)
        return self.async_show_form(
            step_id="pat",
            data_schema=vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str}),
            errors=errors,
        )
