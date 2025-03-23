import requests
import json
import logging
from pprint import pprint
from typing import Dict, List, Optional, Any

class WaniKaniAPI:
    """
    A client for the WaniKani API to retrieve information about kanji characters.
    
    This class provides methods to query the WaniKani API for information about
    kanji characters, including readings, meanings, and radical breakdowns.
    
    API documentation: https://docs.api.wanikani.com/
    """
    
    BASE_URL = "https://api.wanikani.com/v2"
    
    def __init__(self, api_token: str):
        """
        Initialize the WaniKani API client.
        
        Args:
            api_token: The WaniKani API token for authentication.
                       Can be obtained from https://www.wanikani.com/settings/personal_access_tokens
        """
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Wanikani-Revision": "20170710",
            "Content-Type": "application/json"
        }
        self.logger = logging.getLogger(__name__)
    
    def get_kanji_info(self, kanji: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific kanji character from WaniKani.
        
        Args:
            kanji: The kanji character to query.
            
        Returns:
            A dictionary containing information about the kanji, including:
            - readings: Dictionary with primary and alternative readings
            - meanings: List of meanings in English
            - radicals: List of radicals that make up the kanji
            - level: WaniKani level
            
        Raises:
            Exception: If the API request fails or the kanji is not found.
        """
        if not kanji or len(kanji) != 1:
            self.logger.error(f"Invalid kanji: {kanji}. Must be a single character.")
            return None
            
        try:
            # First, search for the kanji to get its subject ID
            search_url = f"{self.BASE_URL}/subjects"
            params = {
                "types": "kanji",
                "slugs": kanji
            }
            
            response = requests.get(search_url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data.get("data") or len(data["data"]) == 0:
                self.logger.warning(f"Kanji not found in WaniKani: {kanji}")
                return None
                
            # Find the exact kanji match
            kanji_data = None
            for item in data["data"]:
                if item["data"]["characters"] == kanji:
                    kanji_data = item
                    break
                    
            if not kanji_data:
                self.logger.warning(f"Exact kanji match not found in WaniKani: {kanji}")
                return None

            print("Got WaniKani Results:")
            pprint(kanji_data, indent=2)
            print()
                
            # Extract the relevant information
            result = {
                "readings": {
                    "onyomi": [],
                    "kunyomi": []
                },
                "meanings": [],
                "level": kanji_data["data"].get("level"),
                "component_subject_ids": kanji_data["data"].get("component_subject_ids", [])
            }
            
            # Extract readings
            for reading in kanji_data["data"].get("readings", []):
                reading_type = reading.get("type")
                reading_value = reading.get("reading")
                if reading_type == "onyomi" and reading_value:
                    result["readings"]["onyomi"].append(reading_value)
                elif reading_type == "kunyomi" and reading_value:
                    result["readings"]["kunyomi"].append(reading_value)
            
            # Extract meanings
            for meaning in kanji_data["data"].get("meanings", []):
                if meaning.get("meaning"):
                    result["meanings"].append(meaning["meaning"])
            
            # If there are component subject IDs, get the radical information
            if result["component_subject_ids"]:
                result["radicals"] = self._get_radicals(result["component_subject_ids"])
            
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error querying WaniKani API: {str(e)}")
            raise Exception(f"Failed to query WaniKani API: {str(e)}")
    
    def _get_radicals(self, subject_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Get information about radicals by their subject IDs.
        
        Args:
            subject_ids: List of subject IDs for the radicals.
            
        Returns:
            A list of dictionaries containing information about each radical.
        """
        radicals = []
        
        try:
            # Query each radical by ID
            for subject_id in subject_ids:
                url = f"{self.BASE_URL}/subjects/{subject_id}"
                response = requests.get(url, headers=self.headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Only include if it's a radical
                    if data["object"] == "radical":
                        radical_info = {
                            "characters": data["data"].get("characters"),
                            "meaning": next((m["meaning"] for m in data["data"].get("meanings", []) 
                                           if m.get("primary")), None),
                            "image_url": data["data"].get("character_images", [{}])[0].get("url") 
                                        if data["data"].get("character_images") else None
                        }
                        radicals.append(radical_info)
                else:
                    self.logger.warning(f"Failed to get radical with ID {subject_id}: {response.status_code}")
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error querying radicals: {str(e)}")
        
        return radicals 

if __name__ == "__main__":
    # Load config file
    import json, sys
    try:
        with open("config.json") as f:
            config = json.load(f)
            api_key = config.get("wanikani_api_token")
            if not api_key:
                print("No WaniKani API key found in config.json")
                sys.exit(1)
    except FileNotFoundError:
        print("config.json not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Invalid JSON in config.json")
        sys.exit(1)

    wanikani = WaniKaniAPI(api_key)

    while True:
        print("Kanji:")
        kanji = input().strip()
        if kanji == "exit" or kanji == "x":
            break

        if len(kanji) != 1:
            print("Please enter only one kanji character.")
            continue
        
        pprint(wanikani.get_kanji_info(kanji))
