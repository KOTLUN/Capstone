from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Test if variables are loaded
client_id = os.getenv('GOOGLE_OAUTH_CLIENT_ID')
client_secret = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET')

print("Client ID loaded:", "Yes" if client_id else "No")
print("Client Secret loaded:", "Yes" if client_secret else "No") 