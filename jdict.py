import os, sys
# try to import jamdict from lib folder
ADDON_PATH = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.join(ADDON_PATH, "lib")
if not os.path.exists(LIB_PATH):
    os.makedirs(LIB_PATH)
sys.path.insert(0, LIB_PATH)
from jamdict import Jamdict
jdict = Jamdict()

def get_english_meanings(japanese_word):    
    # Look up the word
    result = jdict.lookup(japanese_word)
    
    # Extract meanings
    meanings = []
    
    # Process entries from JMdict (Japanese-English dictionary)
    if result.entries:
        for entry in result.entries:
            # Get all senses (meanings)
            for sense in entry.senses:
                # Extract English glosses
                glosses = [gloss.text for gloss in sense.gloss]
                if glosses:
                    meanings.append("; ".join(glosses))
    
    return "\n".join(meanings)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        for word in sys.argv[1:]:
            print(get_english_meanings(word))
    else:
        while True:
            word = input("Enter a Japanese word: ").strip()
            print(get_english_meanings(word))
