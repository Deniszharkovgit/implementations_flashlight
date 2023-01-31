import asyncio
import logging
import pathlib
import sys
from contextlib import suppress

import aiohttp
from aiohttp import web

from flashlight_state import listen_to_commands
from aiohttp.web_runner import GracefulExit

routes = web.RouteTableDef()
logger: logging.Logger = logging.getLogger(__name__)
absolute_path = pathlib.Path(__file__).parent.resolve()


@routes.get("/")
async def index(request):
    return web.FileResponse(f'{absolute_path}/../static/index.html')


@routes.get("/flashlight.js")
async def flashlight_js(request):
    return web.FileResponse(f'{absolute_path}/../static/flashlight.js')


@routes.get("/api/flashlight/current_state")
async def current_state_of_flashlight(request: web.Request):
    return web.json_response(get_current_state(request.app))


def get_current_state(app: web.Application):
    is_turned_on = app["is_flashlight_on"]
    color = app["flashlight_color"]
    response_dict = {"is_turned_on": bool(is_turned_on), "color": f"#{int(color):06x}"}
    return response_dict


@routes.get("/api/flashlight/ws")
async def websocket_handler(request: web.Request):
    logger.debug('Websocket connection starting')
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    clients = request.app["flashlight_clients"]
    try:
        clients.add(ws)
        async for msg in ws:
            if msg == "close":
                break

    finally:
        clients.remove(ws)

    logger.debug('Websocket connection finished')
    return ws


async def broadcast(_app: web.Application):
    """ Разослать обновление всем клиентам. Очень наивная реализация, уязвима к медленным клиентам."""

    list_of_clients: list[web.WebSocketResponse] = _app["flashlight_clients"]
    state = get_current_state(_app)
    for ws in list_of_clients:
        await ws.send_json(state)


async def run_listening_to_commands(_app: web.Application):
    # default values
    _app["is_flashlight_on"] = True
    _app["flashlight_color"] = 0xdeadbeef

    _app["flashlight_clients"] = set()
    task = asyncio.create_task(listen_to_commands(_app, broadcast))

    def halt_if_exception(_fut):
        exception = _fut.exception()
        if exception:
            logger.error("Unhandled exception in worker coroutine. I am stopping my work...")
            raise GracefulExit() from exception

    task.add_done_callback(halt_if_exception)
    yield
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)

    app = web.Application()
    app["remote_commands_host"] = "127.0.0.1"
    app["remote_commands_port"] = 9999

    app.add_routes(routes)
    app.cleanup_ctx.append(run_listening_to_commands)
    web.run_app(app)
