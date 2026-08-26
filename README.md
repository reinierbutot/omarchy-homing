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

## Chromium profiles

Chromium, Chrome, Brave, Edge, Vivaldi, and Helium share one window class across profiles. Homing reads `/proc` (command line, mapped files) to find `--profile-directory` / the profile folder, then looks up the friendly name in `Local State`.

You can home:

- every window of that browser, or
- only this profile (for example Chromium **Work** vs **Private**)

## Homing Chromium Profile (Shortcuts)

First, look up the 'Profile Path' on the `chrome://version` page of your Chromium profile. That is typically `~/.config/chromium/Default` for the first profile and `~/.config/chromium/Profile 1` for a second one. Use the directory name (`Default` and `Profile 1` in this example) in each `.desktop` file so the shortcuts stay distinct.

My Work Shortcut file:
```
[Desktop Entry]
Version=1.0
Type=Application
Name=Chromium (Work)
Comment=Launch Chromium Work Profile
Exec=chromium --profile-directory="Default" --class="chromium-work" %U
Icon=chromium
Terminal=false
StartupNotify=true
Categories=Network;WebBrowser;
StartupWMClass=chromium (Default)
```

My Private Shortcut file :
```
[Desktop Entry]
Version=1.0
Type=Application
Name=Chromium (Prive)
Comment=Launch Chromium Prive Profile
Exec=chromium --profile-directory="Profile 1" --class="chromium-prive" %U
Icon=chromium
Terminal=false
StartupNotify=true
Categories=Network;WebBrowser;
StartupWMClass=chromium (Profile 1)
```

Profile rules tag the window on `window.open_early` (before window rules run) and then send that tag to a workspace. Class rules still win for everything else.

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
homing           # pin the focused window (default)
homing unpin     # remove an assignment
homing list
homing status
homing reload    # rewrite the Lua and hyprctl reload
homing hook      # ask to add the one-line hyprland.lua loader
homing uninstall # remove generated files and the hyprland.lua hook (asks first)
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
