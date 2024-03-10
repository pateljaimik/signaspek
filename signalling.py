import asyncio
import json
import websockets

from aiortc import RTCIceCandidate, RTCSessionDescription
from aiortc.sdp import candidate_from_sdp, candidate_to_sdp

BYE = object()

def object_from_string(message_str):
    message = json.loads(message_str)
    message_data = None
    print(f"Original message: {message}\n")
    if("data" in message.keys()):
        message_data = message["data"]
    if message["what"] == "call":
        return "start"
    elif message["what"] in ["answer", "offer"]:
        return RTCSessionDescription(**message_data)
    elif message["what"] == "iceCandidate" :
        if message_data is None:
            return "Dummy"
        candidate = candidate_from_sdp(message_data["candidate"].split(":", 1)[1])
        candidate.sdpMid = message_data["sdpMid"]
        candidate.sdpMLineIndex = message_data["sdpMLineIndex"]
        return candidate
    elif message["what"] == "hangup":
        print(f"Hanging up with message {message}\n")
        return BYE


def object_to_string(obj):
    if isinstance(obj, RTCSessionDescription):
        message = {"what": obj.type ,
                   "data": {
                       "sdp":obj.sdp,
                       "type": obj.type}}
    elif isinstance(obj, RTCIceCandidate):
        message = {
            "candidate": candidate_to_sdp(obj),
            "sdpMid": obj.sdpMid,
            "sdpMLineIndex": obj.sdpMLineIndex,
        }
        message = {
            "what" : "addIceCandidate",
            "data": message,
        }
    elif isinstance(obj, str) and obj == "start":
        message = {
            "what" : "call",
            "options" : {"force_hw_vcodec": True,
                         "vformat": 30,
                         "trickle_ice": False}
        }
    else:
        assert obj is BYE
        message = {"what": "hangup"}
    print("Sending JSON string: {}\n".format(message))
    return json.dumps(message, sort_keys=True)

class WebsocketSignaling:
    def __init__(self, host, port):
        self._host = host
        self._port = port
        self._websocket = None

    async def connect(self):
        self._websocket = await websockets.connect("ws://" + str(self._host) + ":" + str(self._port)+"/")

    async def close(self):
        if self._websocket is not None and self._websocket.open is True:
            print("Closing web socket")
            await self.send(BYE)
            await self._websocket.close()

    async def receive(self):
        try:
            data = await self._websocket.recv()
        except asyncio.IncompleteReadError: #TODO: replace to occur from websocket connection
            print("IncompleteReadError")
            return
        ret = object_from_string(data)
        if ret == None:
            print("remote host says good bye!")

        return ret

    async def send(self, descr):
        data = object_to_string(descr)
        await self._websocket.send(data )

