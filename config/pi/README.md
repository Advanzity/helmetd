# Pi setup and persistent display

The current bench uses the logged-in user's existing labwc/Wayland desktop.
Put the Pi runtime in `~/helmetd`, then run on the Pi:

```sh
cd ~/helmetd
bash tools/pi/setup.sh
mkdir -p ~/.config/systemd/user ~/.local/state
cp config/pi/helmetd-display.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now helmetd-display
```

The unit starts with the graphical session, restarts on exit, uses
`WAYLAND_DISPLAY=wayland-0`, and appends diagnostics to
`~/.local/state/helmetd-display.log`. It runs as the desktop user, without root.
The user needs access to the video/render devices (the tested account already
belongs to `video` and `render`). No SSH, network, boot or display-mode settings
are changed. Auto-start on a future login is configured but was not reboot-tested.

```sh
systemctl --user show helmetd-display -p MainPID -p NRestarts -p ActiveState
tail -n 20 ~/.local/state/helmetd-display.log
systemctl --user stop helmetd-display
# Disable future automatic starts as well:
systemctl --user disable helmetd-display
```

Use `systemctl --user edit helmetd-display` for a different checkout, Wayland
socket, port or jitter budget. Clear `ExecStart=` before replacing it. A unit
reload does not restart the running receiver; apply changes deliberately when
the live demo can be interrupted. Do not run two receivers on the same UDP port.

The Mac sender needs the Pi's LAN address. The capture sender needs the Mac's
LAN address; see [capture](../../apps/capture/README.md). Host-specific values
belong in ignored `*.local.*` files or `.local/`. Never store SSH passwords or
other credentials in repository files.
