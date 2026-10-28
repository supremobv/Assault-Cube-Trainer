# Appearance and configuration profiles

Open **Configuration** in RangeLab. Appearance preferences work independently of the game connection, but require the matching ESP, radar or crosshair control to be enabled before appearing in-game.

- Toggle ESP boxes, names, health, armour and distance separately.
- Set enemy/ally colors, ESP line thickness and text size.
- Choose a plus, dot or circle crosshair, its color, size, gap and thickness. Gaps larger than the chosen crosshair are clamped when drawn.
- Set radar pixel size separately from its world-unit radius.
- Aim activation, cone, smoothing and range are configured in **Aim & firing** and saved with profiles.

Enter a profile name and select **Save current**. Profiles include numeric presets, currently enabled controls, aim options and appearance. They are stored in `%LOCALAPPDATA%\RangeLab\profiles` as ordinary JSON files. Saving the same name replaces that profile atomically after validation.

Choose/enter its name and select **Load profile**. Loading first restores current trainer controls, then applies the saved preferences/presets. **Controls do not activate by default.** To activate saved controls too, connect first and check **Activate compatible saved controls when loading**. Incompatible controls are skipped; the status line reports the count, and its tooltip includes reasons. No profile activates automatically on app launch.

Profiles reject unknown settings, invalid ranges, conflicting control combinations and path traversal. They are parsed as data and never executed. No chat messages, name changes, teleport actions or other one-time actions run merely from loading a profile.

## Cheat Engine appearance preset

The CT includes **Trainer | Visual preferences (edit preset; uncheck to reapply)**. Edit the final `RangeLabCE.configureVisuals({...})` block in its Auto Assembler script, then enable the entry. Uncheck/recheck to reapply edits. The preset changes overlay preferences only; enabling it alone does not turn on ESP or write game memory.

The same setting names are available through `RangeLabCE.configureVisuals` in CE Lua, for example:

```lua
RangeLabCE.configureVisuals({
  esp_boxes = true,
  esp_names = true,
  esp_health = true,
  esp_armour = true,
  crosshair_style = "circle",
  crosshair_color = "#FFAA00",
  crosshair_size = 12
})
```

The app's JSON profile files are not imported automatically by CE. Save CT preset edits in the table for persistence. Native CE timer/rendering behavior still needs confirmation; Lua 5.3 validation and preset execution are tested with a CE API adapter.
