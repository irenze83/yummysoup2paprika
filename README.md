# yummysoup2paprika

Convert an old **YummySoup!** recipe library into a **Paprika Recipe Manager 3** archive (`.paprikarecipes`).

`yummysoup2paprika` is an independent, unofficial tool for converting user-owned YummySoup! recipe libraries into a Paprika Recipe Manager 3 compatible export file.
This project was created to help users recover recipes from YummySoup! libraries that can no longer be opened on recent macOS versions.

## What it converts

The converter reads a YummySoup! library package or ZIP archive and creates a Paprika 3 import archive.

It currently converts:

- recipe names
- ingredients
- directions
- descriptions
- notes and private notes
- categories / keywords
- cuisine
- prep time
- cook time
- servings / yield
- ratings
- source URLs
- main photos
- secondary photos up to `Image10`
- YummySoup photo references such as `[2]`, converting them to Paprika references such as `[photo:2]`

## Requirements

- Python 3.11 or later
- No third-party Python packages

## Disclaimer

This project is an independent, unofficial conversion tool.

It is not affiliated with, endorsed by, sponsored by, or associated with YummySoup!, Paprika Recipe Manager, Hindsight Labs LLC, or any past or present developer, publisher, or rights holder of those applications.

YummySoup! and Paprika Recipe Manager are trademarks or product names of their respective owners. They are mentioned here only to describe the purpose of this conversion tool: helping users migrate their own recipe data from a YummySoup! library to a Paprika-compatible export file.

This tool does not include, distribute, or replicate any part of the YummySoup! or Paprika applications. It only reads user-owned local data files and generates a new export file based on the user's own recipe content.

## Usage

### From the source checkout

```bash
python3 -m yummysoup2paprika \
  "YummySoup! Library.library.zip" \
  "YummySoup converted.paprikarecipes"
```

You can also use an extracted `.library` package:

```bash
python3 -m yummysoup2paprika \
  "YummySoup! Library.library" \
  "YummySoup converted.paprikarecipes"
```

### Test on a small subset first

```bash
python3 -m yummysoup2paprika \
  "YummySoup! Library.library.zip" \
  "YummySoup test.paprikarecipes" \
  --limit 10
```

Then import the test archive into Paprika and check a few recipes before converting the full library.

## Importing into Paprika

In Paprika Recipe Manager 3, use:

**File → Import**

and select the generated `.paprikarecipes` file.

For large libraries with many photos, import may take a while. Let Paprika finish even if it appears quiet for some time.

## Backups and safety

This tool does not modify the original YummySoup! library. It only reads from it and creates a new Paprika archive.

Still, before using it, make a backup of:

- your original `YummySoup! Library.library` or `.zip`
- the generated `.paprikarecipes` archive
- an HTML export from Paprika after importing, for long-term preservation

## Known limitations

- The converter was developed from a real YummySoup! library and a Paprika 3 export, but YummySoup! versions may differ.
- Ingredient parsing supports the OpenStep-style ingredient format seen in tested YummySoup! libraries.
- Secondary photo support assumes YummySoup filenames in the form `<unique-id>-Image2.jpg`, `<unique-id>-Image3.jpg`, etc.
- Paprika preview appearance is controlled by Paprika; the converter preserves the full image data.

## Privacy

Do not publish your personal recipe library, database, or exported recipe archive in issues or pull requests. If you need to report a bug, prefer a tiny artificial sample or redact private data first.

## License

MIT. See [LICENSE](LICENSE).
