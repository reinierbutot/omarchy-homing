# Homing

Home an app to a Hyprland workspace from the window you are looking at. Next time it opens, it lands there.

Omarchy configures Hyprland in Lua, so Homing writes `~/.config/hypr/homing.lua` instead of editing `hyprland.conf`. The picker is the same overlay menu as the rest of Omarchy (`omarchy-menu-select`).

## Use it

Focus the window, then:

- **Super+Shift+H**
- Omarchy menu → Trigger → **Home this app**
- `omarchy-shell shell summon reinier.homing`
- `~/.config/omarchy/plugins/reinier.homing/bin/homing`

Pick a workspace (1–10, any extra named ones, or Custom). Homing overwrites an existing rule for that app instead of stacking duplicates, reloads Hyprland, and moves the current window.

If nothing is focused, you get an overlay saying so rather than a silent no-op.

## Chromium profiles

Chromium, Chrome, Brave, Edge, Vivaldi, and Helium share one window class across profiles. Homing reads `/proc` (command line, mapped files) to find `--profile-directory` / the profile folder, then looks up the friendly name in `Local State`.

You can home:

- every window of that browser, or
- only this profile (for example Chromium **Work** vs **Private**)

## Homing Chromium Profile (Shortcuts)

First, look up the 'Profile Path' on the `chrome://version` page, of your Chromium profile. For me that is `/home/reinier/.config/chromium/Default` for my Work profile and `/home/reinier/.config/chromium/Profile 1` for my private profile. Then use the directory name (`Default` and `Profile 1` in my case) and use those in each .desktop file to distinguish it from the other Chromium shortcut.

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
| `~/.config/omarchy/homing/assignments.json` | Source of truth |
| `~/.config/hypr/homing.lua` | Generated Hyprland rules (do not edit) |
| `*.bak` next to those files | Previous copy, taken before each write |
| `~/.config/hypr/hyprland.lua` | One-line `pcall(require, "hypr.homing")` hook |

## Commands

```
homing          # pin the focused window (default)
homing unpin    # remove an assignment
homing list
homing status
homing reload   # rewrite the Lua and hyprctl reload
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

Then bind or summon as above. First pin also injects the Hyprland hook if it is missing.
