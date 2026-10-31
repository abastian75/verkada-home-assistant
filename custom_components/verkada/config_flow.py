"""Native Home Assistant setup, reauthentication and options."""

import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AuthenticationError, PermissionError, VerkadaClient, VerkadaError
from .const import DEFAULT_OPTIONS, DOMAIN, REGIONS


def connection_schema(defaults=None):
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required("name", default=defaults.get("name", "Verkada")): str,
            vol.Required("region", default=defaults.get("region", "us")): selector.SelectSelector(
                selector.SelectSelectorConfig(options=list(REGIONS), translation_key="region")
            ),
            vol.Required("org_id", default=defaults.get("org_id", "")): str,
            vol.Required("api_key"): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
            vol.Optional("streaming_api_key", default=""): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
            ),
        }
    )


async def validate(hass, data):
    try:
        data["org_id"] = str(uuid.UUID(data["org_id"].strip()))
    except (ValueError, AttributeError) as err:
        raise vol.Invalid("invalid_org") from err
    data["api_key"] = data["api_key"].strip()
    if not data["api_key"]:
        raise AuthenticationError("API key is empty")
    data["streaming_api_key"] = data.get("streaming_api_key", "").strip()
    api = VerkadaClient(
        async_get_clientsession(hass),
        data["region"],
        data["api_key"],
        data["org_id"],
        data["streaming_api_key"],
    )
    await api.cameras()


class VerkadaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await validate(self.hass, user_input)
                await self.async_set_unique_id(f"{user_input['region']}_{user_input['org_id']}")
                self._abort_if_unique_id_configured()
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except PermissionError:
                errors["base"] = "missing_permission"
            except VerkadaError:
                errors["base"] = "cannot_connect"
            except vol.Invalid:
                errors["org_id"] = "invalid_org"
            else:
                user_input["webhook_id"] = uuid.uuid4().hex
                return self.async_create_entry(title=user_input["name"], data=user_input)
        return self.async_show_form(
            step_id="user", data_schema=connection_schema(user_input), errors=errors
        )

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input:
            data = {**entry.data, **user_input}
            try:
                await validate(self.hass, data)
                await self.async_set_unique_id(f"{data['region']}_{data['org_id']}")
                self._abort_if_unique_id_mismatch()
            except (AuthenticationError, PermissionError):
                errors["base"] = "invalid_auth"
            except VerkadaError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)
        schema = connection_schema(entry.data)
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input:
            data = {**entry.data, **user_input}
            try:
                await validate(self.hass, data)
                await self.async_set_unique_id(f"{data['region']}_{data['org_id']}")
                self._abort_if_unique_id_mismatch()
            except (AuthenticationError, PermissionError):
                errors["base"] = "invalid_auth"
            except VerkadaError:
                errors["base"] = "cannot_connect"
            except vol.Invalid:
                errors["org_id"] = "invalid_org"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(
            step_id="reconfigure", data_schema=connection_schema(entry.data), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return VerkadaOptionsFlow()


class VerkadaOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            if user_input.get("webhook_secret") and len(user_input["webhook_secret"]) < 16:
                errors["webhook_secret"] = "short_secret"
            else:
                return self.async_create_entry(title="", data=user_input)
        options = {**DEFAULT_OPTIONS, **self.config_entry.options}
        hub = getattr(self.config_entry, "runtime_data", None)
        choices = (
            {cid: camera.get("name", cid) for cid, camera in hub.inventory.items()} if hub else {}
        )
        for cid in (
            options.get("camera_ids", []) + options["lpr_camera_ids"] + options["helix_camera_ids"]
        ):
            choices.setdefault(cid, cid)
        selection = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[{"value": cid, "label": name} for cid, name in choices.items()],
                multiple=True,
            )
        )
        return self.async_show_form(
            step_id="init",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Optional("camera_ids", default=options.get("camera_ids", [])): selection,
                    vol.Required("poll_interval", default=options["poll_interval"]): vol.All(
                        vol.Coerce(int), vol.Range(min=30, max=900)
                    ),
                    vol.Required("alerts", default=options["alerts"]): bool,
                    vol.Optional("lpr_camera_ids", default=options["lpr_camera_ids"]): selection,
                    vol.Optional("helix_event_type", default=options["helix_event_type"]): str,
                    vol.Optional(
                        "helix_camera_ids", default=options["helix_camera_ids"]
                    ): selection,
                    vol.Optional(
                        "helix_plate_attribute", default=options["helix_plate_attribute"]
                    ): str,
                    vol.Optional(
                        "webhook_secret", default=options["webhook_secret"]
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                    vol.Required("history_days", default=options["history_days"]): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=30)
                    ),
                    vol.Required("high_resolution", default=options["high_resolution"]): bool,
                }
            ),
        )
