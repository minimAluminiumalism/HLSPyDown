import requests

key_uri = "https://p2.japronx.com/keys/bbe45cc0125227aab4ff0639d915fca5.key"

index = 1

while index <= 100:
    response = requests.get(key_uri)
    print(response.status_code)
    index += 1