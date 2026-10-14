# What's New

**What's New** is a pyRevit utility for discovering newly added production-ready tools and previously seen tools whose `help.html` has been revised.

On the first normal run it shows the complete installed feature set. After that, it shows only features that are new or whose help content has changed since the last normal run. A **Shift-click** opens the full installed feature catalog without changing the user's seen-feature history.

<p align="center">
  <img src="PyPiPie_Logo.png" alt="PyPiPie Factory Tools" width="180">
</p>

## Features

- Shows all production-ready features on the first normal run.
- Shows newly added features as **NEW** on later normal runs.
- Shows previously seen features with revised `help.html` files as **IMPROVED**.
- Displays **Nothing new** when there are no new or improved features.
- Shift-click always opens the complete feature catalog.
- Shift-click does not modify the user's seen-feature state.
- Branded WPF loading dialog with live feature name and percent complete.
- Branded HTML output.
- Displays each feature's local icon when available.
- Reads feature title, description, type, and date from `help.html` metadata.
- Removes a trailing `- Help`, `– Help`, or `— Help` from displayed feature names.
- Makes both the blue **NEW** badge and amber **IMPROVED** badge open the feature's local help file, just like **Open help**.
- Supports light and dark HTML themes through `prefers-color-scheme`.
- Stores seen-feature history per Windows user.
- Migrates older state formats when possible.
- IronPython 2.7 / pyRevit compatible.

## How It Works

A feature is considered **production ready** when its folder contains a `help.html` file.

What's New scans the extension for those folders and builds a feature ID from each folder's path relative to the extension root. It also stores a content hash for each `help.html`. The feature ID determines whether a feature is new; the stored hash determines whether an already-seen feature has been improved.

This means:

- adding a new feature folder with `help.html` makes it appear as **NEW**;
- changing an existing feature's `help.html` makes it appear once as **IMPROVED**;
- deleting the user's saved state causes the next normal run to behave like a first run.

## Normal Click

A normal click runs `WhatsNew_script.py`.

### First normal run

1. The loading dialog opens.
2. What's New scans the extension for folders containing `help.html`.
3. Every discovered production-ready feature is displayed.
4. The complete feature-ID set and current help-file hashes are written to the user's state file.
5. The written state is immediately read back and verified.

### Later normal runs

1. The saved feature IDs and help-file hashes are loaded.
2. The extension is scanned again.
3. Unseen feature IDs are displayed as **NEW**.
4. Previously seen IDs whose `help.html` hash changed are displayed as **IMPROVED**.
5. The current IDs and hashes are saved as the new baseline.
6. If there are no new or improved features, the resulting page displays **Nothing new**.

## Shift-Click: Full Catalog

Shift-click uses pyRevit's optional `config.py` action.

`config.py` loads the shared What's New implementation and explicitly calls:

```python
main(True)
```

Full-catalog mode:

- shows every discovered production-ready feature;
- marks unseen features with the **NEW** badge;
- marks already-seen features whose help content has changed with **IMPROVED**;
- does **not** modify the saved state;
- is independent of runtime Shift-key detection inside the main script.

This explicit separation is important. Do **not** name the configuration file `config_script.py` when the main file is also named `WhatsNew_script.py`; both names end in `script.py` and can be treated as candidate main scripts by pyRevit. Use `config.py` for the Shift-click action.

## Bundle Structure

Recommended pushbutton contents:

```text
What's New.pushbutton/
├── WhatsNew_script.py
├── config.py
├── Welcome.xaml
├── PyPiPie_Logo.png
├── icon.png
├── help.html
└── bundle.yaml              # optional
```

### Important

Do not leave older competing command files in the same bundle, including:

```text
config_script.py
script.py
```

if `WhatsNew_script.py` is the intended normal command entry point.

After changing executable filenames, reload pyRevit.

## Loading Dialog

`Welcome.xaml` provides the modeless branded loading screen used while the feature list is built.

The Python script expects these named controls:

```text
LogoImage
StatusText
LoadProgress
PercentText
```

During discovery, the dialog reports the current feature being read and updates the determinate progress bar from 0 to 100 percent.

The branding image is searched in this order:

```text
PyPiPie_Logo.png
pypipie_logo.png
icon.png
icon.dark.png
icon.jpg
icon.jpeg
```

## Feature Metadata

Each production-ready feature should contain a `help.html` file.

Recommended `<head>` metadata:

```html
<title>Boolean Regions</title>
<meta name="description" content="Performs Boolean operations on filled and masking regions.">
<meta name="type" content="Tool">
<meta name="date" content="2026-10-14">
```

### Supported values

| Display item | Source |
|---|---|
| Feature name | `<title>` in `help.html`, otherwise folder name |
| Description | `<meta name="description">` |
| Type chip | `<meta name="type">` |
| Date | `<meta name="date" content="YYYY-MM-DD">`, otherwise help-file modified date |
| Help link | The local `help.html` file |
| Icon | Local icon file in the feature folder |

If no type is supplied, bundle folders are shown as **Tool** and other help-bearing folders as **Feature**.

## Feature Icons

What's New looks for the following filenames, in order:

```text
icon.png
icon.dark.png
icon.svg
icon.jpg
icon.jpeg
```

Icons are displayed ahead of the feature name in the resulting HTML. A 64 x 64 px PNG is recommended.

## HTML Output

The generated HTML includes:

- PyPiPie branding;
- feature icon;
- feature title;
- **NEW** badge for unseen features;
- **IMPROVED** badge for previously seen features whose `help.html` changed;
- date;
- extension/panel breadcrumb;
- type chip;
- description;
- **Open help** link.

The blue **NEW** badge and amber **IMPROVED** badge are hyperlinks to the same help page.

Each output page uses a fresh temporary filename so an already-open browser tab does not show stale content from a previous run.

## User State

The active state file is stored in the user's Roaming AppData folder:

```text
%APPDATA%\PyPiPie\WhatsNew\state.json
```

Typical location:

```text
C:\Users\<user>\AppData\Roaming\PyPiPie\WhatsNew\state.json
```

A current state file resembles:

```json
{
  "version": 7,
  "initialized": true,
  "seen_ids": [
    "help:pypipie.tab/tools.panel/example.pushbutton"
  ],
  "feature_hashes": {
    "help:pypipie.tab/tools.panel/example.pushbutton": "9b74c9897bac770ffc029102a200c5de"
  },
  "last_run": "2026-10-14 13:00:00"
}
```

The script writes the state atomically and immediately reads it back to verify that both the expected feature IDs and help-file hashes persisted.

### Resetting What's New

To intentionally make the next normal run show all currently installed features again, delete:

```text
%APPDATA%\PyPiPie\WhatsNew\state.json
```

The next normal run will create a new baseline.

## Legacy State Migration

The script can use older state locations as migration sources, including previous Local AppData and pyRevit state-file formats. Once migrated, the active state is written to the current Roaming AppData location.

## Additional Extension Roots

By default, What's New scans the `.extension` folder containing the command.

Additional extension roots can be added in `WhatsNew_script.py`:

```python
EXTRA_ROOTS = [
    r"C:\Path\To\Another.extension",
]
```

When multiple roots are scanned, the extension name is incorporated into the internal feature ID so identical relative paths in different extensions remain distinct.

## Troubleshooting

### Every normal click shows the full catalog

Check the generated HTML footer.

If it says:

```text
Mode: Shift catalog
```

on a normal click, check the bundle filenames first. The normal command should be `WhatsNew_script.py` and the Shift-click action should be `config.py`. Remove old `config_script.py` or other competing `*script.py` files and reload pyRevit.

If the footer says `Mode: Normal`, inspect the state information and confirm that `state.json` exists and contains `initialized: true` with a nonzero `seen_ids` list after the first run.

### Loading window does not appear

Confirm that:

- `Welcome.xaml` is in the same folder as `WhatsNew_script.py`;
- the required named controls exist;
- the XAML is valid WPF;
- `PresentationFramework`, `PresentationCore`, and `WindowsBase` are available.

If WPF initialization fails, the tool is designed to continue without the loading window.

### Logo does not appear

Place:

```text
PyPiPie_Logo.png
```

in the same folder as `WhatsNew_script.py` and `Welcome.xaml`.

### Feature does not appear

Confirm that the feature folder contains a file named:

```text
help.html
```

The comparison is case-insensitive, but the feature is not considered production ready without that file.

### Existing feature is not shown as IMPROVED after its help page changes

Confirm the normal run has already established a hash baseline for that feature. When upgrading from an older state format that did not store hashes, the first run silently records hashes for previously seen features so the upgrade does not mark the entire catalog as **IMPROVED**. A later edit to that same `help.html` should then appear once as **IMPROVED**.

## Compatibility

The implementation is intended for:

- pyRevit
- IronPython 2.7
- .NET Framework / WPF environments used by supported Revit releases

The code avoids relying on CPython-only features for the production pyRevit path.

## Files

| File | Purpose |
|---|---|
| `WhatsNew_script.py` | Normal command and shared implementation |
| `config.py` | Shift-click full-catalog action |
| `Welcome.xaml` | Modeless progress/loading window |
| `PyPiPie_Logo.png` | Branding used by the loader and HTML |
| `help.html` | In-product help for What's New itself |
| `icon.png` | pyRevit command icon, when provided |
| `bundle.yaml` | Optional pyRevit bundle metadata |

## Design Notes

The tool deliberately uses a simple local JSON state file rather than a project file, Revit model storage, or central database. Seen history is a user-interface preference and therefore remains local to each Windows user.

Feature discovery is also intentionally documentation-driven: adding `help.html` is the signal that a feature is ready to be presented to users.

## License

Use the same license applied to the parent PyPiPie extension/repository.

---

**PyPiPie Factory Tools**  
What's New utility
