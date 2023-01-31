import asyncio
import logging
from enum import Enum
from typing import Optional, AsyncIterable, Callable, Coroutine, Any

from aiohttp import web
from pydantic.class_validators import root_validator
from pydantic.error_wrappers import ValidationError
from pydantic.main import BaseModel

logger: logging.Logger = logging.getLogger(__name__)


class CommandType(str, Enum):
    ON = "ON",
    OFF = "OFF",
    COLOR = "COLOR"


class CommandDTO(BaseModel):
    command: CommandType
    metadata: Optional[float]

    class Config:
        use_enum_values = True

    @root_validator(allow_reuse=True)
    def validate_metadata_is_present_for_color_command(cls, values):
        color = values.get("metadata")
        if values.get("command") == CommandType.COLOR:
            if color is None:
                raise ValueError("We consider color command with missing color value as invalid one.")
        return values


async def _read_remote_commands(host: str, port: int, max_reconnect_tries: int = 5) -> AsyncIterable[CommandDTO]:
    writer = None
    try:
        attempt = 1
        while attempt <= max_reconnect_tries:
            logger.info("Opening connection to %s:%d (attempt %d)", host, port, attempt)
            reader, writer = await asyncio.open_connection(host, port)
            logger.info("Connection established for %s:%d (attempt %d)", host, port, attempt)

            while not reader.at_eof():
                try:
                    raw_command: bytes = await reader.readuntil(b"}")
                    current_command: CommandDTO = CommandDTO.parse_raw(raw_command)
                    yield current_command
                except ValidationError as e:
                    logger.warning("The validation of command failed so we skip it: %s", e)
                except EOFError:
                    logger.error("Connection closed unexpectedly. I will try to reconnect")
                    break

    except asyncio.CancelledError:
        pass
    except ConnectionError as e:
        logger.error("There was an issue during connect: %s", e)
        logger.exception(e)
        raise e
    finally:
        if writer:
            writer.close()


async def listen_to_commands(app: web.Application, on_command = None):
    host = app["remote_commands_host"]
    port = app["remote_commands_port"]
    async for message in _read_remote_commands(host, port):
        match [message.command, message.metadata]:
            case [CommandType.ON, _]:
                logger.debug("ON")
                app["is_flashlight_on"] = True

            case [CommandType.OFF, _]:
                logger.debug("OFF")
                app["is_flashlight_on"] = False

            case [CommandType.COLOR, new_color]:
                logger.debug("COLOR %s", new_color)
                app["flashlight_color"] = new_color

            case _:
                logger.warning("Unknown command: %s", message.command)
                continue

        if on_command:
            await on_command(app)
