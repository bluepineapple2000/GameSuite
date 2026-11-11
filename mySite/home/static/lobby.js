"use strict";
const lobby = document.getElementById("lobby");
const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const socket = new WebSocket(`${protocol}//${window.location.host}/ws/room/${lobby.dataset.roomId}/`);
socket.onmessage = (message) => {
    if (JSON.parse(message.data).event === "lobby_changed") window.location.reload();
};
socket.onclose = (event) => {
    if (event.code === 4403) {
        window.location.assign("/imposterGame/");
    } else {
        document.getElementById("connection-status").textContent = "Verbindung unterbrochen. Lade die Seite neu, um dich wieder zu verbinden.";
    }
};
