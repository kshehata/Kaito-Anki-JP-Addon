import requests

def load_image_from_url(url):
    """Load an image from a URL and return a QPixmap."""
    response = requests.get(url, timeout=5)
    if response.status_code != 200:
        raise Exception(f"Failed to load image: HTTP {response.status_code}")
    
    return response.content

class ChatGPT:
    def __init__(self, config):
        self.api_key = config["openai_api_key"]
        self.mnemonics_prompt_template = config.get("chatgpt_mnemonics_prompt_template", 
                               "Write a short (< 100 words) story as a mnemonic for remembering the Japanese word '{japanese_text}' meaning '{english_text}'. Write 4 such stories, each separated by 2 new lines. Make the stories short and memorable, connecting the pronunciation to the meaning.")
        self.image_prompt_template = config.get("chatgpt_image_prompt_template", 
                                "Create a simple, clear illustration to represent'{japanese}' meaning '{english}'. The image should be minimalist and educational.")
        self.mnemonic_image_prompt_template = config.get(
            "chatgpt_mnemonic_image_prompt_template", 
            "Illustrate the following story: {story}")

    def text_query(self, prompt):
        """Issue a query to ChatGPT and get the response."""
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that creates memorable mnemonics for language learning."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            },
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception("Failed to generate mnemonics with ChatGPT: " + str(response.json()))
        
        data = response.json()
        if "choices" not in data or len(data["choices"]) < 1:
            return []
        
        # Extract the content from the response
        return data["choices"][0]["message"]["content"]
        
        # Split the content by double newlines to get individual stories
        stories = [story.strip() for story in content.split("\n\n") 
                if story.strip() and len(story.strip()) >= 10]
        # print("Stories: " + str(stories))
        return stories

    def gen_mnemonics(self, japanese_text, english_text):
        """Generate mnemonic stories."""
        # print("Shortcutting mnemonics")
        # return ['**Story 1:**  \nIn a lush forest, a **rin**g of friends gathered under the **go**lden apple tree. They picked shiny **ringo** apples, laughing and sharing tales about their adventures. The sweet scent of apples filled the air, reminding them of their joyful bond.', '**Story 2:**  \nOnce upon a time, a wise old **rin**gmaster invited children to his magical **go**lden apple orchard. Each child picked a **ringo** apple that granted a wish, making their dreams come true in the enchanting land of fruit.', '**Story 3:**  \nA curious **rin**o found a **go**lden apple on the ground. He took a bite and felt a surge of energy, realizing it was a magical **ringo** that would help him explore the vast forest and make new friends.', '**Story 4:**  \nIn a quaint village, a young girl named **Rin** loved to bake. One day, she decided to make a pie with fresh **go**lden **ringo** apples from the market, filling her home with a delightful aroma that brought everyone together.']
        prompt = self.mnemonics_prompt_template.format(japanese_text=japanese_text, english_text=english_text)
        content = self.text_query(prompt)
        
        # Split the content by double newlines to get individual stories
        stories = [story.strip() for story in content.split("\n\n") 
                if story.strip() and len(story.strip()) >= 10]
        return stories

    def image_query(self, prompt):
        """Helper to generate an image using ChatGPT for the given prompt."""
        
        # print("Shortcutting image generation")
        # url = "https://oaidalleapiprodscus.blob.core.windows.net/private/org-gKiTH4bzIh5r71w1xXJo1Exi/user-pdf8FzTUpzng0o5c2LriNjgZ/img-AFs6rjBSndiKg1DqxyCwuQA0.png?st=2025-03-11T09%3A52%3A45Z&se=2025-03-11T11%3A52%3A45Z&sp=r&sv=2024-08-04&sr=b&rscd=inline&rsct=image/png&skoid=d505667d-d6c1-4a0a-bac7-5c84a87759f8&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-03-10T23%3A18%3A50Z&ske=2025-03-11T23%3A18%3A50Z&sks=b&skv=2024-08-04&sig=bDJsJ2m4O8Qzaaez5zvom0WSOscMGG3J8wzQx8BRHQA%3D"
        # url = "https://files.oaiusercontent.com/file-JA1s3hdSFoBs9TSoF5hm1d?se=2025-03-09T10%3A01%3A41Z&sp=r&sv=2024-08-04&sr=b&rscc=max-age%3D604800%2C%20immutable%2C%20private&rscd=attachment%3B%20filename%3Ddd5bc415-0348-465b-8170-a9126235c22a.webp&sig=lRo5nv0qkp6zIWAdVAfNh8AMsv32inKJtAd%2BAzOf1a8%3D"
        # image = load_image_from_url(url)

        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024"
            },
            timeout=30
        )

        if response.status_code != 200:
            raise Exception("Failed to generate image with ChatGPT: " + str(response.json()))
        
        data = response.json()
        if "data" not in data or len(data["data"]) < 1:
            return None
        image = load_image_from_url(data["data"][0]["url"])

        return {
            "url": data["data"][0]["url"],
            "image": image,
            "source": "ChatGPT",
            "title": "AI Generated Image"
        }

    def gen_prompt_image(self, japanese_text, english_text):
        """Generate an image using ChatGPT based on the Japanese and English text."""
        prompt = self.image_prompt_template.format(japanese=japanese_text, english=english_text)
        # print("ChatGPT Prompt Image Prompt: " + prompt)
        return self.image_query(prompt)
        # print("Shortcutting ChatGPT")
        # url = 'https://oaidalleapiprodscus.blob.core.windows.net/private/org-gKiTH4bzIh5r71w1xXJo1Exi/user-pdf8FzTUpzng0o5c2LriNjgZ/img-GXGaApbaUCxVmD4QonHGWdXM.png?st=2025-03-09T05%3A48%3A15Z&se=2025-03-09T07%3A48%3A15Z&sp=r&sv=2024-08-04&sr=b&rscd=inline&rsct=image/png&skoid=d505667d-d6c1-4a0a-bac7-5c84a87759f8&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-03-08T22%3A05%3A50Z&ske=2025-03-09T22%3A05%3A50Z&sks=b&skv=2024-08-04&sig=vnvJo1l%2BFNrapSjii5Wwqwqvi/r%2BPsn9qdtRKlaFvMA%3D'
        # return {
        #     "url": url,
        #     "thumbnail": load_image_from_url(url),
        #     "source": "ChatGPT",
        #     "title": "AI Generated Image"
        # }

    def gen_mnemonic_image(self, story):
        """Generate an image using ChatGPT based on the mnemonic story."""

        prompt = self.mnemonic_image_prompt_template.format(story=story)
        return self.image_query(prompt)

def print_image_result(result):
    print(result["url"] if result else "No result")

if __name__ == "__main__":
    # Load config file
    import json, sys
    try:
        with open("config.json") as f:
            config = json.load(f)
            api_key = config.get("openai_api_key")
            if not api_key:
                print("No OpenAI API key found in config.json")
                sys.exit(1)
    except FileNotFoundError:
        print("config.json not found")
        sys.exit(1)
    except json.JSONDecodeError:
        print("Invalid JSON in config.json")
        sys.exit(1)

    chatgpt = ChatGPT(config)
    while True:
        print("Commands:")
        print("  [m]mnemonics <japanese> <english>")
        print("  [i]mage <prompt>")
        print("  [p]rompt <japanese> <english>")
        print("  [s]toryimage <story>")
        print("  e[x]it")
        command = input().strip()
        if command == "exit" or command == "x":
            break
        parts = command.split()
        if not parts:
            continue
            
        if parts[0].startswith("m"):
            if len(parts) < 3:
                print("Usage: m <japanese> <english>")
                continue
            try:
                print("Querying ChatGPT for mnemonics...")
                result = chatgpt.gen_mnemonics(parts[1], parts[2])
                print(result)
            except Exception as e:
                print("Error generating mnemonics: " + str(e))
                
        elif parts[0].startswith("i"):
            if len(parts) < 2:
                print("Usage: i <prompt>") 
                continue
            try:
                prompt = command[len(parts[0]):].strip()
                print("Querying ChatGPT for image from prompt: " + prompt)
                result = chatgpt.image_query(prompt)
                print_image_result(result)
            except Exception as e:
                print("Error generating image: " + str(e))
                
        elif parts[0].startswith("p"):
            if len(parts) < 3:
                print("Usage: p <japanese> <english>") 
                continue
            try:
                print("Querying ChatGPT for image prompt...")
                result = chatgpt.gen_prompt_image(parts[1], parts[2])
                print_image_result(result)
            except Exception as e:
                print("Error generating image: " + str(e))
                
        elif parts[0].startswith("s"):
            if len(parts) < 2:
                print("Usage: s <prompt>") 
                continue
            try:
                prompt = command[len(parts[0]):].strip()
                print("Querying ChatGPT for image for story: " + prompt)
                result = chatgpt.gen_mnemonic_image(prompt)
                print_image_result(result)
            except Exception as e:
                print("Error generating image: " + str(e))
                
        else:
            print("Unknown command: " + parts[0])
