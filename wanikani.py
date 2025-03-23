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

    def _query(self, query: str, query_type: str) -> Optional[Dict[str, Any]]:
        """
        Internal helper for querying the WaniKani API.
        """

        if not query:
            return None
            
        try:
            search_url = f"{self.BASE_URL}/subjects"
            params = {
                "types": query_type,
                "slugs": query,
            }
            
            response = requests.get(search_url, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            if not data.get("data") or len(data["data"]) == 0:
                return None

            return data
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error querying WaniKani API: {str(e)}")
            raise Exception(f"Failed to query WaniKani API: {str(e)}")
    
    def _query_subject_ids(self, subject_ids: List[int]) -> Optional[Dict[str, Any]]:
        """
        Query the WaniKani API for information about the components of a subject.
        """
        if not subject_ids:
            return None
            
        try:
            results = []
            for subject_id in subject_ids:
                url = f"{self.BASE_URL}/subjects/{subject_id}"
                response = requests.get(url, headers=self.headers)
                
                if response.status_code != 200:
                    self.logger.warning(f"Failed to get subject with ID {subject_id}: {response.status_code}")
                    continue

                results.append(response.json())

            return results
        
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Error querying WaniKani API: {str(e)}")
            raise Exception(f"Failed to query WaniKani API: {str(e)}")
    
    
    def _extract_meanings(self, meanings: List[Dict[str, Any]]) -> List[str]:
        """
        Extract the meanings from the WaniKani API response.
        """
        results = []
        for meaning in meanings:
            if meaning.get("meaning"):
                results.append(meaning["meaning"])
        return results
    
    def get_vocab_info(self, vocab: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific vocabulary word from WaniKani.
        """
        if not vocab:
            self.logger.error(f"Empty vocab query.")
            return None

        data = self._query(vocab, "vocabulary")
        if not data:
            self.logger.error(f"No data found for vocab: {vocab}")
            return None

        # Just use the first result, should always be correct.
        vocab_data = data["data"][0]["data"]

        # Get info for any kanji components
        kanji_data = self._get_kanji_from_ids(vocab_data.get("component_subject_ids", []))

        result = {
            "vocab": vocab_data.get("characters"),
            "meanings": self._extract_meanings(vocab_data.get("meanings")),
            "kanji": kanji_data,
            "reading_mnemonic": vocab_data["reading_mnemonic"],
            "meaning_mnemonic": vocab_data.get("meaning_mnemonic"),
        }
        return result

    def _convert_kanji_data(self, kanji_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Extract the relevant information
        result = {
            "readings": {
                "onyomi": [],
                "kunyomi": []
            },
            "meanings": [],
            "level": kanji_data["data"].get("level"),
            "component_subject_ids": kanji_data["data"].get("component_subject_ids", []),
            "meaning_mnemonic": kanji_data["data"].get("meaning_mnemonic"),
            "meaning_hint": kanji_data["data"].get("meaning_hint"),
            "reading_mnemonic": kanji_data["data"].get("reading_mnemonic"),
            "reading_hint": kanji_data["data"].get("reading_hint")
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

    def _get_kanji_from_ids(self, ids: List[int]) -> Optional[Dict[str, Any]]:
        kanji_data = self._query_subject_ids(ids)
        if not kanji_data:
            self.logger.error(f"No data found for kanji IDs: {ids}")
            return None

        return [self._convert_kanji_data(kanji) for kanji in kanji_data]
        
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
            
        data = self._query(kanji, "kanji")
        # Find the exact kanji match
        kanji_data = None
        for item in data["data"]:
            if item["data"]["characters"] == kanji:
                kanji_data = item
                break
                
        if not kanji_data:
            self.logger.warning(f"Exact kanji match not found in WaniKani: {kanji}")
            return None

        return self._convert_kanji_data(kanji_data)
            
    def _get_radicals(self, subject_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Get information about radicals by their subject IDs.
        
        Args:
            subject_ids: List of subject IDs for the radicals.
            
        Returns:
            A list of dictionaries containing information about each radical.
        """
        radicals = []
        data_items = self._query_subject_ids(subject_ids)
        for data in data_items:
            if data["object"] != "radical": continue
            radical_info = {
                "characters": data["data"].get("characters"),
                "meaning": next((m["meaning"] for m in data["data"].get("meanings", []) 
                                if m.get("primary")), None),
                "image_url": data["data"].get("character_images", [{}])[0].get("url") 
                            if data["data"].get("character_images") else None
            }
            radicals.append(radical_info)

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
        # print("Kanji:")
        # kanji = input().strip()
        # if kanji == "exit" or kanji == "x":
        #     break

        # if len(kanji) != 1:
        #     print("Please enter only one kanji character.")
        #     continue
        
        # pprint(wanikani.get_vocab_info(kanji))

        print("Vocab:")
        vocab = input().strip()
        if vocab == "exit" or vocab == "x":
            break

        pprint(wanikani.get_vocab_info(vocab))
