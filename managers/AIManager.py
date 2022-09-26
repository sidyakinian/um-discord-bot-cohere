from dotenv import load_dotenv
import sys, os, base64, datetime, hashlib, hmac, requests, json
import cohere

load_dotenv()

class AIManager(object):
    def __init__(self):
        api_key = os.environ['COHERE_API_KEY']
        self.co = cohere.Client(api_key)

    async def complete_prompt(self, inputs):
        response = self.co.classify(
            model=os.environ['COHERE_MODEL_ID'],
            inputs=[inputs],
            examples=[]
        )
        response_labels = response.classifications[0].labels
        most_likely_label = max(response_labels, key = lambda k: response_labels.get(k).confidence)
        return most_likely_label