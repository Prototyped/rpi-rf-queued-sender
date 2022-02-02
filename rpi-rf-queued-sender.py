#!/usr/bin/python3
from collections.abc import Callable
from flask import Flask, Request, Response, request, jsonify
from functools import partial
import json
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError
from multiprocessing import Process, Queue
from rpi_rf import RFDevice
import time


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
        print(f'Sent code {code} to GPIO pin {gpio}. Sleeping a bit.')
        time.sleep(0.5)

    @classmethod
    def _create_rfdevice(cls, gpio) -> RFDevice:
        return RFDevice(gpio, tx_repeat=50)


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

    def __init__(self, queue: Queue):
        self.queue = queue
        self.validator = Draft202012Validator(schema=self.SCHEMA)

    def handle(self, request: Request) -> Response:
        shape = request.get_json()
        try:
            self.validator.validate(shape)
        except ValidationError as exc:
            return f'Request validation failed: {exc.message}', 400

        self.queue.put(shape)
        return jsonify({})


def dequeue_and_send(queue: Queue) -> None:
    sender = Sender()

    while True:
        try:
            message = queue.get()
            sender.send(message['gpioPin'], message['code'])
            print(f'Enqueued message {message}')
        except UnicodeDecodeError as exc:
            print(f'Failed to decode message {message}: {exc}')
        except Exception as exc:
            print(f'Failed to process message: {type(exc).__name__}: {exc}.')


def main() -> None:
    queue = Queue()
    handler = RequestHandler(queue)
    process = Process(target=partial(dequeue_and_send, queue))
    process.daemon = True
    process.start()

    app = Flask(__name__)

    @app.route('/send', methods=['POST'])
    def send() -> Response:
        return handler.handle(request)

    app.run(host='127.0.0.1', port=58080)
    process.join()


if __name__ == '__main__':
    main()
