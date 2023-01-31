function handle_state(state) {
    const flashlight = document.getElementById("flashlight")
    flashlight.innerText = state["is_turned_on"] ? "ON" : "OFF";
    flashlight.style.background = state["color"];
}

window.onload = (ev) => {
    fetch("/api/flashlight/current_state").then(r => r.json()).then(state => handle_state(state));
    const ws = new WebSocket("ws://" + window.location.host + "/api/flashlight/ws");

    ws.onmessage = (event) => {
        handle_state(JSON.parse(event.data));
    }
}
