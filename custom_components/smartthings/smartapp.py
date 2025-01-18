"""SmartApp functionality to receive cloud-push notifications."""

import asyncio
import functools
import logging
import secrets
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from aiohttp import web
from pysmartapp import Dispatcher, SmartAppManager
from pysmartapp.const import SETTINGS_APP_ID
from pysmartthings import (
    APP_TYPE_WEBHOOK,
    CAPABILITIES,
    CLASSIFICATION_AUTOMATION,
    App,
    AppEntity,
    AppOAuth,
    AppSettings,
    InstalledAppStatus,
    SmartThings,
    SourceType,
    Subscription,
    SubscriptionEntity,
)

from homeassistant.components import cloud, webhook
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.network import NoURLAvailableError, get_url
from homeassistant.helpers.storage import Store

from .const import (
    APP_NAME_PREFIX,
    APP_OAUTH_CLIENT_NAME,
    APP_OAUTH_SCOPES,
    CONF_CLOUDHOOK_URL,
    CONF_INSTALLED_APP_ID,
    CONF_INSTANCE_ID,
    CONF_REFRESH_TOKEN,
    DATA_BROKERS,
    DATA_MANAGER,
    DOMAIN,
    IGNORED_CAPABILITIES,
    SETTINGS_INSTANCE_ID,
    SIGNAL_SMARTAPP_PREFIX,
    STORAGE_KEY,
    STORAGE_VERSION,
    SUBSCRIPTION_WARNING_LIMIT,
)

_LOGGER = logging.getLogger(__name__)

async def smartapp_sync_subscriptions(
    hass: HomeAssistant,
    auth_token: str,
    location_id: str,
    installed_app_id: str,
    devices,
):
    """Synchronize subscriptions of an installed app."""
    api = SmartThings(async_get_clientsession(hass), auth_token)
    tasks = []

    async def create_subscription(target: str):
        sub = Subscription()
        sub.installed_app_id = installed_app_id
        sub.location_id = location_id
        sub.source_type = SourceType.CAPABILITY
        sub.capability = target
        try:
            await api.create_subscription(sub)
            _LOGGER.debug(
                "Created subscription for '%s' under app '%s'", target, installed_app_id
            )
        except Exception as error:
            _LOGGER.error(
                "Failed to create subscription for '%s' under app '%s': %s",
                target,
                installed_app_id,
                error,
            )

    async def delete_subscription(sub: SubscriptionEntity):
        try:
            await api.delete_subscription(installed_app_id, sub.subscription_id)
            _LOGGER.debug(
                "Removed subscription for '%s' under app '%s' because it was no longer needed",
                sub.capability,
                installed_app_id,
            )
        except Exception as error:
            _LOGGER.error(
                "Failed to remove subscription for '%s' under app '%s': %s",
                sub.capability,
                installed_app_id,
                error,
            )

    # Build set of capabilities and prune unsupported ones
    capabilities = set()
    for device in devices:
        capabilities.update(device.capabilities)
    _LOGGER.debug("Available capabilities: %s", capabilities)

    capabilities.intersection_update(CAPABILITIES)
    capabilities.difference_update(IGNORED_CAPABILITIES)
    capability_count = len(capabilities)
    if capability_count > SUBSCRIPTION_WARNING_LIMIT:
        _LOGGER.warning(
            "Too many subscriptions required (%d), exceeding limit (%d)",
            capability_count,
            SUBSCRIPTION_WARNING_LIMIT,
        )

    _LOGGER.debug(
        "Synchronizing subscriptions for %d capabilities under app '%s': %s",
        capability_count,
        installed_app_id,
        capabilities,
    )

    # Get current subscriptions and find differences
    subscriptions = await api.subscriptions(installed_app_id)
    for subscription in subscriptions:
        if subscription.capability in capabilities:
            capabilities.remove(subscription.capability)
        else:
            tasks.append(delete_subscription(subscription))

    # Remaining capabilities need subscriptions created
    tasks.extend([create_subscription(c) for c in capabilities])

    if tasks:
        await asyncio.gather(*tasks)
    else:
        _LOGGER.debug("Subscriptions for app '%s' are up-to-date", installed_app_id)


async def smartapp_webhook(hass: HomeAssistant, webhook_id: str, request):
    """Handle a SmartApp lifecycle event callback from SmartThings."""
    manager = hass.data[DOMAIN][DATA_MANAGER]
    data = await request.json()

    _LOGGER.debug("Received SmartApp webhook data: %s", data)

    try:
        result = await manager.handle_request(data, request.headers)
        return web.json_response(result)
    except Exception as e:
        _LOGGER.error("Error processing webhook: %s", e)
        return web.Response(status=500)
