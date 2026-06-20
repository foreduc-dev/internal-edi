import requests
from bs4 import BeautifulSoup

session = requests.Session()
url = "https://arms.sse.saveetha.com/Login.aspx"

response = session.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

viewstate = soup.find('input', {'name': '__VIEWSTATE'})
viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})

payload = {
    'txtUsername': 'Ssetssh239',
    'txtPassword': 'Ssetssh239',
    'btnLogin': 'Login'
}

if viewstate:
    payload['__VIEWSTATE'] = viewstate['value']
if viewstategenerator:
    payload['__VIEWSTATEGENERATOR'] = viewstategenerator['value']
if eventvalidation:
    payload['__EVENTVALIDATION'] = eventvalidation['value']

print("Sending payload keys:", payload.keys())
post_response = session.post(url, data=payload)
print("Status code:", post_response.status_code)
print("Cookies:", session.cookies.get_dict())
print("Response URL:", post_response.url)
