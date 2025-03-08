# Kaito's Japanese Anki Addon

This addon helps with creating Japanese language flashcards in Anki by providing:

1. Automatic reading generation for Japanese text
2. Definition lookup using JMdict
3. Image search and selection using Google Images

## Setup

### Basic Setup

1. Install the addon through Anki's addon manager
2. Configure the fields in the addon configuration:
   - `srcField`: The field containing Japanese text (default: "Japanese")
   - `englishField`: The field for English definitions (default: "English")
   - `imageField`: The field for images (default: "Image")

### Google Custom Search API Setup (Optional)

To enable the image search feature, you need to set up Google Custom Search API:

1. Create a Google Cloud Platform project at https://console.cloud.google.com/
2. Enable the "Custom Search API" for your project
3. Create API credentials (API key) at https://console.cloud.google.com/apis/credentials
4. Create a Custom Search Engine at https://programmablesearchengine.google.com/
   - Set it to search the entire web
   - Enable "Image search" option
   - Get your Search Engine ID (cx)
5. In Anki, go to Tools > Add-ons > Kaito's Japanese Addon > Config
6. Add your API key to the `google_api_key` field
7. Add your Search Engine ID to the `google_cx` field

If you don't configure the Google API, the addon will open Google Images in your browser instead.

## Usage

1. Create a new card in a Japanese note type
2. Enter Japanese text in the source field
3. Click the "Kaito's Japanese Magic" button in the editor toolbar
4. The wizard will guide you through:
   - Confirming the reading
   - Editing the definition
   - Selecting an image for the word

## Requirements

- Anki 2.1.45+
- Python 3.7+
- Required Python packages:
  - jamdict
  - requests

## Troubleshooting

### Image Search Issues

- **API Key or Search Engine ID not configured**: Make sure you've added both your Google API key and Custom Search Engine ID (cx) in the addon configuration.
- **API Error messages**: Check that your API key is valid and has the Custom Search API enabled. Also verify that billing is set up if you've exceeded the free quota.
- **No images displayed**: Ensure your Custom Search Engine is configured to search the entire web and has Image Search enabled.
- **Error loading images**: This may be due to network issues or timeout. Try again later.
- **PyQt compatibility errors**: If you encounter errors related to QFrame or other Qt components, please report them in the issues section with your Anki version. These are typically caused by differences between PyQt versions.

### API Quota Limits

- The Google Custom Search API has a free tier of 100 search queries per day
- If you need more, you'll need to enable billing on your Google Cloud Platform account

### Common Error Messages

- **"QFrame has no attribute Box/StyledPanel"**: This is a PyQt version compatibility issue. The latest version of the addon uses a simpler approach without frame styles.
- **"type object 'Qt' has no attribute 'AlignCenter'"**: Another PyQt version compatibility issue. The latest version avoids using Qt alignment constants.
- **"setAlignment(self, a0: Qt.AlignmentFlag): argument 1 has unexpected type 'int'"**: PyQt version compatibility issue. The latest version avoids setting alignment flags.
- **"API Error: ..."**: This indicates an issue with your Google API configuration. The specific error message should provide more details.
- **"Error searching for images: ..."**: Check your internet connection and try again. If the problem persists, check the Anki error log for more details.

## License

This addon is licensed under the MIT License. 