# WebVisionKit Student Docs

WebVisionKit is a pixels-in, actions-out framework. Your app sees rendered browser frames, decides what to do, and sends browser input actions back through the runtime.

## Start Here

- Build the runtime image once: `./infrastructure/docker/build.bash`
- Check your environment: `./launch.bash doctor`
- Start the full launcher: `./launch.bash`
- Run a small reference bot: `APP_NAME=simple_drag TARGET_URL_OVERRIDE=game://simple_drag ./launch.bash`

## How The Framework Works

WebVisionKit keeps Chrome on the host and runs your code inside Docker. The runtime streams browser frames into your app, your `on_frame(...)` callback inspects those pixels, and your app queues input actions such as clicks, drags, scrolls, and key presses.

- Google Chrome runs on the host with DevTools remote debugging enabled.
- `./launch.bash` prepares Chrome, Docker, and the selected app.
- The `webvisionkit` runtime and your app run inside the container.
- Chrome DevTools Protocol (CDP) delivers screencast frames to the runtime.
- Your app returns observations and browser actions for the runtime to dispatch.

## What You Can Build

- Observation-only bots that report what is on screen.
- Screenshot capture tools that save frames for later analysis.
- Game-playing bots that detect features and act on them.
- Input-lab calibration agents that practice pointer, drag, scroll, text, and keyboard inputs.

## Read Next

- [Framework Overview](framework.md)
- [webvisionkit API](api.md)
- [Practical Examples](examples.md)
- [Troubleshooting](troubleshooting.md)
