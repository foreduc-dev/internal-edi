import requests
url = "https://arms.sse.saveetha.com/Handler/Testmark.ashx?Page=TestNamebyCourse&Mode=TestNamebyCourse&CourseId=123"
r = requests.get(url)
print(r.status_code)
print(r.url)
print(len(r.text))
