# Homing

Home an app to a Hyprland workspace from the window you are looking at. Next time it opens, it lands there.

Omarchy configures Hyprland in Lua, so Homing writes `~/.config/hypr/homing.lua` instead of editing `hyprland.conf`. The picker is the same overlay menu as the rest of Omarchy (`omarchy-menu-select`).

Homing never edits your Hyprland config on install. The first time you home an app, it asks before adding one line to `~/.config/hypr/hyprland.lua` so Hyprland loads the generated rules. Decline, and nothing is written there; add `pcall(require, "hypr.homing")` yourself, or run `homing hook` later.

## Use it

Focus the window, then:

- `omarchy-shell shell summon reinier.homing`
- `~/.config/omarchy/plugins/reinier.homing/bin/homing`
- a keybind you add yourself, for example Super+Shift+H (Homing does not write `bindings.lua`)

Pick a workspace (1–10, any extra named ones, or Custom). Homing replaces an existing rule for that app instead of stacking duplicates, reloads Hyprland, and moves the current window.

If nothing is focused, you get an overlay saying so rather than a silent no-op.

Optional keybind in `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + SHIFT + H", "Home this app to a workspace", os.getenv("HOME") .. "/.config/omarchy/plugins/reinier.homing/bin/homing")
```

## Chromium profiles & shortcuts

Chromium-based browsers (Chromium, Chrome, Brave, Edge, Vivaldi, Helium) can be homed in two ways:

### 1. Isolated Profiles with Custom Window Classes (Recommended)

Chromium runs a single master process per `--user-data-dir`. If two shortcuts share the same user data directory (`~/.config/chromium`), Chromium forwards subsequent launches to the running master process via IPC, causing subsequent windows to inherit the master process's PID and Wayland window class.

To give each profile completely independent processes and distinct window classes (`chromium-work`, `chromium-prive`) that match fast native Hyprland window rules, specify a dedicated `--user-data-dir`, `--profile-directory`, and `--class` (with matching `StartupWMClass`):

**Work shortcut (`~/.local/share/applications/chromium-work.desktop`):**
```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=Chromium (Work)
Comment=Launch Chromium Work Profile
Exec=chromium --user-data-dir=/home/username/.config/chromium-work --profile-directory="Default" --class="chromium-work" %U
Icon=chromium
Terminal=false
StartupNotify=true
Categories=Network;WebBrowser;
StartupWMClass=chromium-work
```

**Private shortcut (`~/.local/share/applications/chromium-prive.desktop`):**
```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=Chromium (Prive)
Comment=Launch Chromium Prive Profile
Exec=chromium --user-data-dir=/home/username/.config/chromium-prive --profile-directory="Profile 1" --class="chromium-prive" %U
Icon=chromium
Terminal=false
StartupNotify=true
Categories=Network;WebBrowser;
StartupWMClass=chromium-prive
```

Focus each browser window and run `homing pin` to assign it to its designated workspace. Homing will generate clean, static `hl.window_rule`s matching `class = "^(chromium-work)$"` and `class = "^(chromium-prive)$"`.

### 2. Browser Tab Discovery & Accessibility (AT-SPI / Everything)

By default on Linux, Chromium disables its AT-SPI accessibility bridge to minimize memory overhead. When disabled, tab switchers and search plugins (such as Omarchy's **Everything** plugin) cannot discover or index open browser tabs across your profiles.

To enable full browser tab discovery for all Chromium profiles:

#### Quick Automated Fix
Run Homing's built-in doctor command:
```sh
~/.config/omarchy/plugins/reinier.homing/bin/homing doctor --fix
```
Then close and restart any open Chromium browser instances.

#### What this configures:
1. **Desktop Toolkit Accessibility**:
   Enables the AT-SPI desktop interface in GSettings so applications know the accessibility bus is active:
   ```sh
   gsettings set org.gnome.desktop.interface toolkit-accessibility true
   ```
2. **Persistent Environment Variable**:
   Ensures `ACCESSIBILITY_ENABLED=1` is loaded in every desktop session via `~/.config/environment.d/accessibility.conf`:
   ```sh
   mkdir -p ~/.config/environment.d
   echo "ACCESSIBILITY_ENABLED=1" >> ~/.config/environment.d/accessibility.conf
   systemctl --user import-environment ACCESSIBILITY_ENABLED
   dbus-update-activation-environment --systemd ACCESSIBILITY_ENABLED=1
   ```
3. **Chromium Launcher Flags**:
   Appends `--force-renderer-accessibility` to `~/.config/chromium-flags.conf` so Chromium's web renderers always build accessibility trees for tab enumeration:
   ```sh
   echo "--force-renderer-accessibility" >> ~/.config/chromium-flags.conf
   ```

*Note on Web Apps / PWAs*: Windows launched in standalone app mode (`--app=https://...`, e.g. via `omarchy-launch-webapp`) do not possess a browser tab strip. Tab search tools like Everything intentionally treat PWA windows as top-level application windows rather than tab items.

### 3. Dynamic Single-Instance Profile Homing

If you share a single `~/.config/chromium` data directory without `--class` flags, all windows share the standard browser class (`chromium`). Homing detects the active profile by reading `/proc` (command line and mapped files) and checking `Local State`.

When pinning, Homing will ask whether you want to home:
- every window of that browser, or
- only this specific profile (e.g. **Work** vs **Private**)

Profile rules tag the window on `window.open_early` (before window rules run) and move that tag to the designated workspace. Class rules still apply for regular apps.

## Files

| Path | Role |
|---|---|
| `~/.config/omarchy/homing/assignments.json` | Source of truth (created when you home an app). Browser profile dirs are stored as `$XDG_CONFIG_HOME/...` or `~/...`, then resolved for the current user when Homing writes `homing.lua`. |
| `~/.config/hypr/homing.lua` | Generated Hyprland rules (do not edit) |
| `*.bak` next to those two files | Previous copy of Homing's own files |
| `~/.config/hypr/hyprland.lua` | Touched only if you agree to add `pcall(require, "hypr.homing")` |
| `~/.config/hypr/hyprland.lua.homing.bak` | One-time copy of `hyprland.lua` from before that hook was added |

## Commands

```
homing                 # pin the focused window (default)
homing unpin           # remove an assignment
homing list            # list homed apps and workspaces
homing status          # show focused window class, profile, and browser a11y status
homing doctor          # diagnose hook, assignments, and tab discovery / AT-SPI setup
homing doctor --fix    # automatically repair hook and configure browser tab discovery
homing reload          # rewrite the Lua and hyprctl reload
homing hook            # ask to add the one-line hyprland.lua loader
homing uninstall       # remove generated files and the hyprland.lua hook (asks first)
```

## Why not `windowrulev2`?

Hyprland 0.55 dropped hyprlang. The equivalent of

```
windowrulev2 = workspace 3, class:^(slack)$
```

is a Lua window rule:

```lua
hl.window_rule({
  name = "homing-class-slack",
  match = { class = "^(slack)$" },
  workspace = "3",
})
```

Class names are RE2-escaped (`com.mitchellh.ghostty` does not become a wildcard). Chromium-family classes expand to `chromium` / `Chromium-browser`.

## Install

```sh
omarchy plugin add https://github.com/reinierbutot/omarchy-homing.git --enable
```

That only clones the plugin and enables it in Omarchy. It does not edit Hyprland config, keybinds, or menus. Summon or bind as above. The first pin asks before adding the Hyprland hook.

## Remove

```sh
~/.config/omarchy/plugins/reinier.homing/bin/homing uninstall
omarchy plugin remove reinier.homing
```

`homing uninstall` asks first, then:

- removes the `pcall(require, "hypr.homing")` hook from `~/.config/hypr/hyprland.lua` if it is present
- deletes `~/.config/hypr/homing.lua` and `~/.config/omarchy/homing/`

If you added a Super+Shift+H bind, delete that line from `~/.config/hypr/bindings.lua`. Then `hyprctl reload`.

## Requirements

Omarchy Quattro (Hyprland Lua config, `omarchy-menu-select`, `omarchy-notification-send`) and Python 3. No extra packages.

## License

MIT. See [LICENSE](LICENSE).
