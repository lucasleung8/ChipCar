# ChipCar
A full-stack remote control car controllable anywhere in the world, built by the Raspberry Pi team at McMaster to showcase in future workshops. Using a Raspberry Pi alongside Python, Flask, JavaScript, WebSockets (SocketIO) for real-time communication and user authentication, live video stream using OpenCV, sound system with a horn, multithreaded performance with gunicorn, and securely deployed via Cloudflare Tunnel. Try it at [chipcar.cc](https://chipcar.cc)!

## Build Instructions
Run ``run.sh``, changing the motor pin numbers if required.

## Environment Configuration
These variables need to be set:

- USER_PASSWORD (replace USER with the corresponding username)
- ADMIN_PASSWORD
