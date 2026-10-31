"""Share useful counts/status without organization IDs, events or credentials."""


async def async_get_config_entry_diagnostics(hass, entry):
    hub = entry.runtime_data
    return {
        "region": entry.data["region"],
        "camera_count": len(hub.data),
        "history_count": len(hub.events),
        "poll_interval": hub.options["poll_interval"],
        "sources": [
            {
                "state": status["state"],
                "message": status.get("message"),
                "last_success": status.get("last_success"),
            }
            for status in hub.status.values()
        ],
        "coordinator_success": hub.last_update_success,
    }
