import requests
from bs4 import BeautifulSoup

session = requests.Session()
url = "https://arms.sse.saveetha.com/Login.aspx"
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
}
response = session.get(url, headers=headers)
soup = BeautifulSoup(response.text, 'html.parser')

payload = {}
for input_tag in soup.find_all('input'):
    name = input_tag.get('name')
    if name:
        payload[name] = input_tag.get('value', '')

# Replace the specific ones
if 'txtusername' in payload:
    payload['txtusername'] = 'Ssetssh239'
elif 'txtUsername' in payload:
    payload['txtUsername'] = 'Ssetssh239'
    
if 'txtpassword' in payload:
    payload['txtpassword'] = 'Ssetssh239'
elif 'txtPassword' in payload:
    payload['txtPassword'] = 'Ssetssh239'

print("Payload:", payload)
post_response = session.post(url, data=payload, headers=headers)
print("Status:", post_response.status_code)
print("URL:", post_response.url)
if "Object moved" in post_response.text or post_response.status_code == 302 or len(post_response.history) > 0:
    print("Login successful (redirect)")
else:
    print("Login failed, title:", BeautifulSoup(post_response.text, 'html.parser').title.text if BeautifulSoup(post_response.text, 'html.parser').title else "No title")
