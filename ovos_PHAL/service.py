from ovos_plugin_manager.phal import find_phal_plugins
from ovos_config import Configuration
from ovos_utils.log import LOG
from ovos_bus_client.client import MessageBusClient
from ovos_utils.process_utils import ProcessStatus, StatusCallbackMap


def on_ready():
    LOG.info('PHAL is ready.')


def on_stopping():
    LOG.info('PHAL is shutting down...')


def on_error(e='Unknown'):
    LOG.error(f'PHAL failed to launch ({e}).')


def on_alive():
    LOG.info('PHAL is alive')


def on_started():
    LOG.info('PHAL is started')


class PHAL:
    """
    Args:
        config (dict): PHAL config, usually from mycroft.conf
        bus (MessageBusClient): mycroft messagebus connection
        watchdog: (callable) function to call periodically indicating
                  operational status.
    """

    def __init__(self, config=None, bus=None,
                 on_ready=on_ready, on_error=on_error,
                 on_stopping=on_stopping, on_started=on_started, on_alive=on_alive,
                 watchdog=lambda: None, skill_id="ovos.PHAL", **kwargs):
        if not bus:
            bus = MessageBusClient()
            bus.run_in_thread()
        self.skill_id = skill_id
        self.bus = bus

        ready_hook = kwargs.get('ready_hook', on_ready)
        error_hook = kwargs.get('error_hook', on_error)
        stopping_hook = kwargs.get('stopping_hook', on_stopping)
        alive_hook = kwargs.get('alive_hook', on_alive)
        started_hook = kwargs.get('started_hook', on_started)
        callbacks = StatusCallbackMap(on_ready=ready_hook,
                                      on_error=error_hook,
                                      on_stopping=stopping_hook,
                                      on_alive=alive_hook,
                                      on_started=started_hook)
        self.status = ProcessStatus("PHAL", callback_map=callbacks)
        self._watchdog = watchdog  # TODO implement
        self.config = config or Configuration().get("PHAL") or {}
        self.drivers = {}
        self.status.bind(self.bus)

    def load_plugins(self):
        for name, plug in find_phal_plugins().items():
            config = self.config.get(name) or {}
            if hasattr(plug, "validator"):
                enabled = plug.validator.validate(config)
            else:
                enabled = config.get("enabled")
            if enabled:
                try:
                    self.drivers[name] = plug(bus=self.bus, config=config)
                    LOG.info(f"PHAL plugin loaded: {name}")
                except Exception:
                    LOG.exception(f"failed to load PHAL plugin: {name}")
                    continue

    def start(self):
        self.status.set_started()
        try:
            self.load_plugins()
            self.status.set_ready()
        except Exception as e:
            LOG.exception(e)
            self.status.set_error(e)

    def shutdown(self):
        self.status.set_stopping()
