CloudPebble.GlobalShortcuts = (function () {
    var global_shortcuts = {};

    $(document).keydown(function (e) {
        if (!e.isDefaultPrevented()) {
            var shortcut = global_shortcuts[CodeMirror.keyName(e)];
            if (shortcut) {
                e.preventDefault();
                shortcut.func(e);
            }
        }
    });

    function shortcut_for_command(command) {
        // If the command is a name like "save", get they key-combo from CodeMirror
        if (!(command.indexOf('-') > -1)) {
            command = _.findKey(CodeMirror.keyMap.default, _.partial(_.isEqual, command));
        }

        // If any of the shortcut items are "platformcmd", convert them to 'Ctrl' or 'Cmd' depending on the platform.
        function key_for_platform(name) {
            if (name.toLowerCase() == "platformcmd") {
                return /Mac/.test(navigator.platform) ? 'Cmd' : 'Ctrl'
            } else return name;
        }

        return command.split('-').map(key_for_platform).join('-');
    }

    return {
        SetShortcutHandlers: function (shortcuts) {
            _.each(shortcuts, function (descriptor, key) {
                var shortcut = shortcut_for_command(key);
                global_shortcuts[shortcut] = {
                    name: descriptor.name ? descriptor.name : key,
                    func: _.isFunction(descriptor) ? descriptor : descriptor.func
                };
            });
        },
        GetShortcuts: function() {
            return global_shortcuts;
        }
    }
})();
