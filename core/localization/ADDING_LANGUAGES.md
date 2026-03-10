# Adding New Languages to BeamSkin Studio

This guide explains how to add a new language translation to BeamSkin Studio.

## Overview

BeamSkin Studio uses a JSON-based localization system. Each language has its own JSON file in the `core/localization/languages/` directory.

## Steps to Add a New Language

### 1. Create a Language File

Create a new JSON file in `core/localization/languages/` with the language code as the filename.

**Examples:**
- `en.json` - English
- `es.json` - Spanish  
- `fr.json` - French
- `de.json` - German
- `ja.json` - Japanese
- `zh.json` - Chinese

**Common language codes:**
- `en` - English
- `es` - Spanish (Español)
- `fr` - French (Français)
- `de` - German (Deutsch)
- `it` - Italian (Italiano)
- `pt` - Portuguese (Português)
- `ru` - Russian (Русский)
- `ja` - Japanese (日本語)
- `zh` - Chinese (中文)
- `ko` - Korean (한국어)
- `ar` - Arabic (العربية)
- `nl` - Dutch (Nederlands)
- `pl` - Polish (Polski)
- `tr` - Turkish (Türkçe)
- `sv` - Swedish (Svenska)
- `no` - Norwegian (Norsk)
- `da` - Danish (Dansk)
- `fi` - Finnish (Suomi)

### 2. Language File Structure

Each language file must have this basic structure:

```json
{
  "_meta": {
    "name": "Language Name in English",
    "native_name": "Language Name in Native Script",
    "flag": "🇺🇸",
    "contributors": ["Your Name Here"]
  },
  
  "common": {
    "ok": "OK",
    "cancel": "Cancel",
    ...
  },
  
  "menu": {
    ...
  },
  
  ...
}
```

### 3. Metadata Section (`_meta`)

The `_meta` section contains information about the language:

```json
"_meta": {
  "name": "French",          // English name of the language
  "native_name": "Français", // Native name (how speakers call it)
  "flag": "🇫🇷",             // Country flag emoji
  "contributors": [          // List of translators (optional)
    "John Doe",
    "Jane Smith"
  ]
}
```

**Finding the Right Flag Emoji:**
- 🇺🇸 United States
- 🇬🇧 United Kingdom  
- 🇪🇸 Spain
- 🇫🇷 France
- 🇩🇪 Germany
- 🇮🇹 Italy
- 🇵🇹 Portugal
- 🇷🇺 Russia
- 🇯🇵 Japan
- 🇨🇳 China
- 🇰🇷 South Korea
- 🇸🇪 Sweden
- And many more...

### 4. Translation Keys

Copy all translation keys from `en.json` (the reference language) and translate each value.

**Important Rules:**
1. **Keep all keys exactly the same** (e.g., `"common.ok"` must stay as `"common.ok"`)
2. **Only translate the values** (the text after the `:`)
3. **Preserve placeholders** like `{name}`, `{version}`, etc.
4. **Keep special characters** like `\n` for line breaks

**Example:**

English (`en.json`):
```json
"generator": {
  "vehicle_settings": "Vehicle Settings for {name}",
  "no_vehicles": "No vehicles added yet"
}
```

French (`fr.json`):
```json
"generator": {
  "vehicle_settings": "Paramètres du véhicule pour {name}",
  "no_vehicles": "Aucun véhicule ajouté"
}
```

### 5. Handling Placeholders

Some strings contain placeholders that will be replaced with dynamic values:

```json
"vehicle_settings": "Vehicle Settings for {name}"
```

When translating, **keep the placeholder**:

```json
"vehicle_settings": "Paramètres du véhicule pour {name}"
```

**Common placeholders:**
- `{name}` - Vehicle or item name
- `{version}` - Version number
- `{language}` - Language name
- `{error}` - Error message

### 6. Testing Your Translation

1. Save your language file in `core/localization/languages/`
2. Restart BeamSkin Studio
3. Go to **Settings** → **Language**
4. Select your language from the dropdown
5. Check all screens for missing or incorrect translations

### 7. Partial Translations

You don't have to translate everything at once! If a translation key is missing:
- The app will show the English text as fallback
- You can add translations incrementally

## Translation Guidelines

### Writing Style

1. **Be Consistent**: Use the same terminology throughout
2. **Match the Tone**: Keep the friendly, helpful tone of the original
3. **Be Concise**: Button labels and menu items should be short
4. **Consider Context**: Some words have different meanings in different contexts

### Technical Terms

Some technical terms might not need translation:
- "DDS" (file format) - usually stays "DDS"
- "PNG" (file format) - usually stays "PNG"  
- "Steam Workshop" - often stays "Steam Workshop"
- "BeamNG.drive" - always stays "BeamNG.drive"

### Common Sections

Here's what each main section contains:

- **common**: Basic UI words (OK, Cancel, Yes, No, etc.)
- **menu**: Main navigation menu items
- **topbar**: Top bar buttons
- **sidebar**: Sidebar labels and buttons
- **generator**: Skin generator tab
- **carlist**: Vehicle list tab
- **add_vehicles**: Add custom vehicles tab
- **settings**: Settings tab
- **howto**: How-to guide tab
- **about**: About tab
- **dialogs**: Dialog boxes and pop-ups
- **notifications**: Notification messages
- **errors**: Error messages

## Example: Adding Japanese

Here's a complete example for Japanese (`ja.json`):

```json
{
  "_meta": {
    "name": "Japanese",
    "native_name": "日本語",
    "flag": "🇯🇵",
    "contributors": ["Your Name"]
  },
  
  "common": {
    "ok": "OK",
    "cancel": "キャンセル",
    "yes": "はい",
    "no": "いいえ",
    "save": "保存",
    "close": "閉じる"
  },
  
  "menu": {
    "generator": "ジェネレーター",
    "carlist": "車両リスト",
    "settings": "設定"
  }
  
  // ... continue with all sections
}
```

## Getting Help

If you need help with translations:

1. Check the English file (`en.json`) for reference
2. Look at other language files for examples
3. Use the context of the UI to understand where text appears
4. Test in the actual application to see how it looks

## Contributing Your Translation

To contribute your translation:

1. Create the language JSON file
2. Test it thoroughly in the application
3. Submit it via:
   - GitHub Pull Request
   - Send to the developer
   - Post in the community Discord/forum

## Quality Checklist

Before submitting your translation:

- [ ] All `_meta` fields are filled correctly
- [ ] Language name and flag emoji are correct  
- [ ] All translation keys from `en.json` are present
- [ ] Placeholders like `{name}` are preserved
- [ ] Translation has been tested in the application
- [ ] No obvious typos or grammatical errors
- [ ] Consistent terminology throughout
- [ ] Appropriate tone and formality level

## Thank You!

Your translation helps make BeamSkin Studio accessible to more people around the world. Thank you for contributing! 🌍
