import Quickshell
import QtQuick

// Headless overlay: summoning Homing launches the CLI, which then uses
// omarchy-menu-select / omarchy-menu-input for the actual UI.
Item {
  id: root

  property var shell: null
  property var manifest: null
  property bool opened: false

  function open(payloadJson) {
    var dir = (root.manifest && root.manifest.__sourceDir) ? String(root.manifest.__sourceDir) : ""
    if (!dir)
      dir = Quickshell.env("HOME") + "/.config/omarchy/plugins/reinier.homing"
    var bin = dir + "/bin/homing"
    var payload = ({})
    try { payload = JSON.parse(payloadJson || "{}") } catch (e) { payload = ({}) }
    var args = [bin]
    if (payload.command) args.push(String(payload.command))
    Quickshell.execDetached(args)
    Qt.callLater(function() {
      if (root.shell && typeof root.shell.hide === "function")
        root.shell.hide((root.manifest && root.manifest.id) || "reinier.homing")
    })
  }

  function close() {
    root.opened = false
  }

  function toggle() {
    root.open("{}")
  }
}
