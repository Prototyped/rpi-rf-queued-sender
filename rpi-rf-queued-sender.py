#!/usr/bin/python3
from collections.abc import Callable
from flask import Flask, Request, Response, request, jsonify
import json
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from multiprocessing import Process
from rpi_rf import RFDevice
import zmq
from zmq.sugar.context import Socket


class Sender:
    def __init__(self, rfdevice_factory: Callable[[int], RFDevice]=None):
        self.rfdevice_factory = rfdevice_factory if rfdevice_factory else Sender._create_rfdevice
        self.rfdevices = {}

    def __del__(self):
        for gpio, rfdevice in self.rfdevices.items():
            rfdevice.cleanup()

    def send(self, gpio: int, code: int) -> None:
        if gpio not in self.rfdevices:
            self.rfdevices[gpio] = self.rfdevice_factory(gpio)
            self.rfdevices[gpio].enable_tx()

        print(f'Sending code {code} to GPIO pin {gpio}')
        self.rfdevices[gpio].tx_code(code)
        print(f'Sent code {code} to GPIO pin {gpio}')

    @classmethod
    def _create_rfdevice(cls, gpio) -> RFDevice:
        return RFDevice(gpio, tx_repeat=200)


class RequestHandler:
    PORT = 51515
    SCHEMA={
        'type': 'object',
        'properties': {
            'gpioPin': {
                'type': 'integer',
                'description': 'Raspberry Pi GPIO pin',
                'minimum': 2,
                'maximum': 27,
            },
            'code': {
                'type': 'integer',
                'description': 'ASK/OOK code to send',
                'minimum': 0,
            },
        },
        'required': ['gpioPin', 'code'],
    }

    def __init__(self, socket: Socket=None, port: int=PORT):
        self.socket = socket if socket else self._create_zmq_socket(port)
        self.validator = Draft202012Validator(schema=self.SCHEMA)

    def handle(self, request: Request) -> Response:
        shape = request.get_json()
        try:
            self.validator.validate(shape)
        except ValidationError as exc:
            return f'Request validation failed: {exc.message}', 400

        self.socket.send(request.data)
        return jsonify({})

    @classmethod
    def _create_zmq_socket(cls, port: int) -> Socket:
        context = zmq.Context()
        socket = context.socket(zmq.DEALER)
        socket.connect(f'tcp://127.0.0.1:{port}')
        return socket


def dequeue_and_send(port: int=RequestHandler.PORT) -> None:
    context = zmq.Context()
    socket = context.socket(zmq.ROUTER)
    print(f'Binding listening socket to tcp://127.0.0.1:{port}')
    socket.bind(f'tcp://127.0.0.1:{port}')
    sender = Sender()

    while True:
        try:
            message = socket.recv()
            content = json.loads(message.decode('UTF-8'))
            sender.send(content['gpioPin'], content['code'])
            print(f'Enqueued message {message}')
        except UnicodeDecodeError as exc:
            print(f'Failed to decode message {message}: {exc}')
        except Exception as exc:
            print(f'Failed to process message: {type(exc).__name__}: {exc}.')


def main() -> None:
    handler = RequestHandler()
    process = Process(target=dequeue_and_send)
    process.start()

    app = Flask(__name__)

    @app.route('/send', methods=['POST'])
    def send() -> Response:
        return handler.handle(request)

    app.run(host='127.0.0.1', port=58080)
    process.join()


if __name__ == '__main__':
    main()
