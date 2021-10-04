"""Support for PlayStation 5 consoles."""
import logging
import os

from psremoteplay.ddp import async_create_ddp_endpoint
from psremoteplay.media_art import COUNTRIES
import voluptuous as vol

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_TITLE,
    MEDIA_TYPE_GAME,
)
from homeassistant.const import (
    ATTR_COMMAND,
    ATTR_ENTITY_ID,
    ATTR_LOCKED,
    CONF_REGION,
    CONF_TOKEN,
)
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.util import location
from homeassistant.util.json import load_json, save_json

from .config_flow import PlayStation5FlowHandler  # noqa: F401
from .const import (
    ATTR_MEDIA_IMAGE_URL,
    COMMANDS,
    COUNTRYCODE_NAMES,
    DOMAIN,
    GAMES_FILE,
    PS5_DATA,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_COMMAND = "send_command"

PS5_COMMAND_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Required(ATTR_COMMAND): vol.In(list(COMMANDS)),
    }
)

PLATFORMS = ["media_player"]


class PS5Data:
    """Init Data Class."""

    def __init__(self):
        """Init Class."""
        self.devices = []
        self.protocol = None


async def async_setup(hass, config):
    """Set up the PS5 Component."""
    hass.data[PS5_DATA] = PS5Data()

    transport, protocol = await async_create_ddp_endpoint()
    hass.data[PS5_DATA].protocol = protocol
    _LOGGER.debug("PS5 DDP endpoint created: %s, %s", transport, protocol)
    service_handle(hass)
    return True


async def async_setup_entry(hass, entry):
    """Set up PS5 from a config entry."""
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload a PS5 config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass, entry):
    """Migrate old entry."""
    config_entries = hass.config_entries
    data = entry.data
    version = entry.version

    _LOGGER.debug("Migrating PS5 entry from Version %s", version)

    reason = {
        1: "Region codes have changed",
        2: "Format for Unique ID for entity registry has changed",
    }

    # Migrate Version 1 -> Version 2: New region codes.
    if version == 1:
        loc = await location.async_detect_location_info(
            hass.helpers.aiohttp_client.async_get_clientsession()
        )
        if loc:
            country = COUNTRYCODE_NAMES.get(loc.country_code)
            if country in COUNTRIES:
                for device in data["devices"]:
                    device[CONF_REGION] = country
                version = entry.version = 2
                config_entries.async_update_entry(entry, data=data)
                _LOGGER.info(
                    "PlayStation 5 Config Updated: \
                    Region changed to: %s",
                    country,
                )

    # Migrate Version 2 -> Version 3: Update identifier format.
    if version == 2:
        # Prevent changing entity_id. Updates entity registry.
        registry = await entity_registry.async_get_registry(hass)

        for entity_id, e_entry in registry.entities.items():
            if e_entry.config_entry_id == entry.entry_id:
                unique_id = e_entry.unique_id

                # Remove old entity entry.
                registry.async_remove(entity_id)

                # Format old unique_id.
                unique_id = format_unique_id(entry.data[CONF_TOKEN], unique_id)

                # Create new entry with old entity_id.
                new_id = split_entity_id(entity_id)[1]
                registry.async_get_or_create(
                    "media_player",
                    DOMAIN,
                    unique_id,
                    suggested_object_id=new_id,
                    config_entry=entry,
                    device_id=e_entry.device_id,
                )
                entry.version = 3
                _LOGGER.info(
                    "PlayStation 5 identifier for entity: %s \
                    has changed",
                    entity_id,
                )
                config_entries.async_update_entry(entry)
                return True

    msg = f"""{reason[version]} for the PlayStation 5 Integration.
            Please remove the PS5 Integration and re-configure
            [here](/config/integrations)."""

    hass.components.persistent_notification.async_create(
        title="PlayStation 5 Integration Configuration Requires Update",
        message=msg,
        notification_id="config_entry_migration",
    )
    return False


def format_unique_id(creds, mac_address):
    """Use last 4 Chars of credential as suffix. Unique ID per PSN user."""
    suffix = creds[-4:]
    return f"{mac_address}_{suffix}"


def load_games(hass: HomeAssistant, unique_id: str) -> dict:
    """Load games for sources."""
    g_file = hass.config.path(GAMES_FILE.format(unique_id))
    try:
        games = load_json(g_file)
    except HomeAssistantError as error:
        games = {}
        _LOGGER.error("Failed to load games file: %s", error)

    if not isinstance(games, dict):
        _LOGGER.error("Games file was not parsed correctly")
        games = {}

    # If file exists
    if os.path.isfile(g_file):
        games = _reformat_data(hass, games, unique_id)
    return games


def save_games(hass: HomeAssistant, games: dict, unique_id: str):
    """Save games to file."""
    g_file = hass.config.path(GAMES_FILE.format(unique_id))
    try:
        save_json(g_file, games)
    except OSError as error:
        _LOGGER.error("Could not save game list, %s", error)


def _reformat_data(hass: HomeAssistant, games: dict, unique_id: str) -> dict:
    """Reformat data to correct format."""
    data_reformatted = False

    for game, data in games.items():
        # Convert str format to dict format.
        if not isinstance(data, dict):
            # Use existing title. Assign defaults.
            games[game] = {
                ATTR_LOCKED: False,
                ATTR_MEDIA_TITLE: data,
                ATTR_MEDIA_IMAGE_URL: None,
                ATTR_MEDIA_CONTENT_TYPE: MEDIA_TYPE_GAME,
            }
            data_reformatted = True

            _LOGGER.debug("Reformatting media data for item: %s, %s", game, data)

    if data_reformatted:
        save_games(hass, games, unique_id)
    return games


def service_handle(hass: HomeAssistant):
    """Handle for services."""

    async def async_service_command(call):
        """Service for sending commands."""
        entity_ids = call.data[ATTR_ENTITY_ID]
        command = call.data[ATTR_COMMAND]
        for device in hass.data[PS5_DATA].devices:
            if device.entity_id in entity_ids:
                await device.async_send_command(command)

    hass.services.async_register(
        DOMAIN, SERVICE_COMMAND, async_service_command, schema=PS5_COMMAND_SCHEMA
    )
