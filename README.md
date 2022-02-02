# rpi-rf-queued-sender

This project is a Flask service that binds to localhost and enqueues requests
to send codes via rpi-rf to specified GPIO pins. It uses
[multiprocessing.Queue](https://docs.python.org/3/library/multiprocessing.html#multiprocessing.Queue)
internally to enqueue and dequeue messages and runs two processes, one to
receive requests and the other to execute them.

This is intended to be used in conjunction with OpenHAB rules that use HTTP
to send requests for rpi-rf.

Each send activity is performed 50 times. Protocol is 1, pulse length is 216
and code length is 24.

## Request format

```json
{
    "gpioPin": 10,
    "code": 12345678
}
```

