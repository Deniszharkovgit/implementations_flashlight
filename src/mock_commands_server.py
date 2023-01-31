import asyncio
import itertools
import logging
import sys

from flashlight_state import CommandDTO, CommandType

logger: logging.Logger = logging.getLogger(__name__)


class MockCommandsProtocol(asyncio.Protocol):
    # будем отправлять командыф каждые 5 секун
    interval_between_commands_in_seconds: int = 5
    commands_to_broadcast: list[CommandDTO] = [CommandDTO(command=CommandType.COLOR, metadata=0xFF69B4),
                                               CommandDTO(command=CommandType.ON),
                                               CommandDTO(command=CommandType.COLOR, metadata=0x00BFFF),
                                               CommandDTO(command=CommandType.OFF)]

    def __init__(self) -> None:
        self._connected_clients = {}

    def connection_made(self, transport: asyncio.Transport):
        peer_name = transport.get_extra_info('peername')
        logger.info("Connection from %s", peer_name)

        asyncio.get_running_loop().create_task(self._push_commands(transport))

    def connection_lost(self, exc: Exception | None) -> None:
        logger.info("Peer disconnected. I am shutting down...")
        asyncio.get_event_loop().stop()

    async def _push_commands(self, transport: asyncio.Transport):
        for command in itertools.cycle(self.commands_to_broadcast):
            logger.debug("Publishing %s", command)
            transport.write(command.json().encode("utf-8"))
            await asyncio.sleep(self.interval_between_commands_in_seconds)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    # Это тестовый сервер для отладки
    loop = asyncio.get_event_loop()
    try:
        coro = loop.create_server(MockCommandsProtocol, "127.0.0.1", 9999)
        loop.run_until_complete(coro)
        loop.run_forever()
    finally:
        loop.close()
