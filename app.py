from flask import Flask, request, jsonify, render_template, session as flask_session, redirect, url_for, flash
import requests
from bs4 import BeautifulSoup
import threading
import functools
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
# Local app credentials for the website login
LOCAL_USERNAME = os.getenv('APP_USER', 'kasif')
LOCAL_PASSWORD = os.getenv('APP_PASS', 'kasifbrothers')

# System credentials used in backend API calls (read from env or fallback to placeholder)
SYSTEM_USERNAME = os.getenv('ARMS_USER', 'Ssetssh239')
SYSTEM_PASSWORD = os.getenv('ARMS_PASS', 'Ssetssh239')

def login_required(f):
    """Enforces authentication for local app routes (UI only)."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not flask_session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == LOCAL_USERNAME and password == LOCAL_PASSWORD:
            flask_session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    flask_session.pop('logged_in', None)
    return redirect(url_for('login'))


class SessionManager:
    """Manages user sessions in memory, with automatic login and token refresh capabilities."""
    def __init__(self):
        # Maps username to a requests.Session() object
        self.sessions = {}
        # Maps username to their password for automatic re-login
        self.credentials = {}
        self.lock = threading.Lock()

    def get_session(self, username, password):
        """Retrieve an existing session or create a new one."""
        with self.lock:
            # If the session exists and password hasn't changed, return it
            if username in self.sessions and self.credentials.get(username) == password:
                return self.sessions[username]
            
            # Otherwise, store the credentials and perform login
            self.credentials[username] = password
            session = self._create_and_login(username, password)
            self.sessions[username] = session
            return session

    def refresh_session(self, username):
        """Re-authenticate using stored credentials when a session expires."""
        with self.lock:
            password = self.credentials.get(username)
            if not password:
                raise ValueError("No credentials found for this user to re-login.")
            
            session = self._create_and_login(username, password)
            self.sessions[username] = session
            return session

    def _create_and_login(self, username, password):
        """Perform the actual login flow and return an authenticated requests.Session."""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        })
        url = "https://arms.sse.saveetha.com/Login.aspx"
        
        try:
            # Step 1: GET the login page to retrieve CSRF tokens (__VIEWSTATE, etc.)
            get_resp = session.get(url, timeout=15)
            get_resp.raise_for_status()
            
            soup = BeautifulSoup(get_resp.text, 'html.parser')
            payload = {}
            
            # Extract all hidden inputs which include CSRF tokens
            for input_tag in soup.find_all('input'):
                name = input_tag.get('name')
                if name:
                    payload[name] = input_tag.get('value', '')
                    
            # Step 2: Inject credentials into the payload
            payload['txtusername'] = username
            payload['txtpassword'] = password
            payload['btnlogin'] = 'Login'
            
            # Step 3: POST the payload to authenticate
            post_resp = session.post(url, data=payload, timeout=15)
            post_resp.raise_for_status()
            
            # Check for successful login (expecting redirect from Login.aspx to another page)
            if "Login.aspx" in post_resp.url and "Object moved" not in post_resp.text:
                raise Exception("Invalid credentials or login failed.")
                
            return session
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error during login: {str(e)}")

# Global instance to manage sessions across requests
session_manager = SessionManager()

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/fetch_testmark', methods=['POST'])
def fetch_testmark():
    data = request.json
    course_id = data.get('courseId')
    username = SYSTEM_USERNAME
    password = SYSTEM_PASSWORD

    if not course_id:
        return jsonify({"error": "courseId is required"}), 400

    url = f"https://arms.sse.saveetha.com/Handler/Testmark.ashx?Page=TestNamebyCourse&Mode=TestNamebyCourse&CourseId={course_id}"
    
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://arms.sse.saveetha.com/FacultyPortal/Attendance.aspx"
    }

    try:
        # Retrieve the authenticated session
        try:
            session = session_manager.get_session(username, password)
        except Exception as e:
            return jsonify({"error": str(e)}), 401

        # Perform the API request
        response = session.get(url, headers=headers, timeout=15)
        
        # Check if the session expired (usually redirects to Login page or gives 401)
        if "Login.aspx" in response.url or response.status_code == 401:
            session = session_manager.refresh_session(username)
            response = session.get(url, headers=headers, timeout=15)
            
        response.raise_for_status()
        
        # Try parsing JSON, fallback to raw text if the response isn't JSON
        try:
            result = response.json()
            return jsonify({"success": True, "data": result})
        except ValueError:
            return jsonify({"success": True, "data": response.text})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/fetch_marklist', methods=['POST'])
def fetch_marklist():
    data = request.json
    course_id = data.get('courseId')
    test_id = data.get('testId')
    username = SYSTEM_USERNAME
    password = SYSTEM_PASSWORD

    if not course_id or not test_id:
        return jsonify({"error": "courseId and testId are required"}), 400

    url = f"https://arms.sse.saveetha.com/Handler/Testmark.ashx?Page=EditMarkEntry&Mode=EditMarkEntry&CourseId={course_id}&TestId={test_id}"
    
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://arms.sse.saveetha.com/FacultyPortal/Attendance.aspx"
    }

    try:
        try:
            session = session_manager.get_session(username, password)
        except Exception as e:
            return jsonify({"error": str(e)}), 401

        response = session.get(url, headers=headers, timeout=15)
        
        # Check if session expired
        if "Login.aspx" in response.url or response.status_code == 401:
            session = session_manager.refresh_session(username)
            response = session.get(url, headers=headers, timeout=15)
            
        response.raise_for_status()
        
        try:
            result = response.json()
            return jsonify({"success": True, "data": result})
        except ValueError:
            return jsonify({"success": True, "data": response.text})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/submit_marks', methods=['POST'])
def submit_marks():
    data = request.json
    course_id = data.get('courseId')
    test_id = data.get('testId')
    username = SYSTEM_USERNAME
    password = SYSTEM_PASSWORD
    competency = data.get('competency', 'Model')
    student_id_list = data.get('studentIdList')
    mark_value_list = data.get('markValueList')

    if not all([course_id, test_id, student_id_list, mark_value_list]):
        return jsonify({"error": "Missing required fields"}), 400

    headers = {
        "Referer": "https://arms.sse.saveetha.com/FacultyPortal/TestMarkEdit.aspx",
        "Origin": "https://arms.sse.saveetha.com"
    }
    
    page_url = "https://arms.sse.saveetha.com/FacultyPortal/TestMarkEdit.aspx"

    try:
        try:
            session = session_manager.get_session(username, password)
        except Exception as e:
            return jsonify({"error": str(e)}), 401

        get_resp = session.get(page_url, headers=headers, timeout=15)
        
        # Check if session expired
        if "Login.aspx" in get_resp.url or get_resp.status_code == 401:
            session = session_manager.refresh_session(username)
            get_resp = session.get(page_url, headers=headers, timeout=15)
            
        get_resp.raise_for_status()
        
        soup = BeautifulSoup(get_resp.text, 'html.parser')
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})
        viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
        
        vs_val = viewstate.get('value', '') if viewstate else ''
        vsg_val = viewstategenerator.get('value', '') if viewstategenerator else ''
        
        payload = {
            '__EVENTTARGET': 'ctl00$cphbody$btnSubmit',
            '__EVENTARGUMENT': '',
            '__VIEWSTATE': vs_val,
            '__VIEWSTATEGENERATOR': vsg_val,
            'ctl00$cphbody$ddlGraduationType': '0',
            'ctl00$cphbody$ddlCourse': course_id,
            'ctl00$cphbody$ddltestname': test_id,
            'ctl00$cphbody$txtCompetency': competency,
            'ctl00$cphbody$HdnCourseId': course_id,
            'ctl00$cphbody$HdnCollgeId': '1',
            'ctl00$cphbody$HdnGraduationId': '0',
            'ctl00$cphbody$hdnStudentIdList': student_id_list,
            'ctl00$cphbody$hdnMarkValue': mark_value_list,
            'ctl00$cphbody$hdnTestId': test_id,
            'ctl00$hdngradeid': '0',
            'ctl00$hdnfeedback': '2'
        }
        
        post_resp = session.post(page_url, data=payload, headers=headers, timeout=15)
        
        # Check if session expired during post
        if "Login.aspx" in post_resp.url or post_resp.status_code == 401:
            session = session_manager.refresh_session(username)
            # Re-fetch page to get valid CSRF tokens
            get_resp = session.get(page_url, headers=headers, timeout=15)
            get_resp.raise_for_status()
            soup = BeautifulSoup(get_resp.text, 'html.parser')
            vs_val = soup.find('input', {'name': '__VIEWSTATE'}).get('value', '')
            vsg_val = soup.find('input', {'name': '__VIEWSTATEGENERATOR'}).get('value', '')
            payload['__VIEWSTATE'] = vs_val
            payload['__VIEWSTATEGENERATOR'] = vsg_val
            post_resp = session.post(page_url, data=payload, headers=headers, timeout=15)
            
        post_resp.raise_for_status()
        
        return jsonify({"success": True, "message": "Marks submitted successfully!"})
        
    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

@app.route('/api/fetch_subjects', methods=['POST'])
def fetch_subjects():
    data = request.json
    reg_no = data.get('regNo')
    username = SYSTEM_USERNAME
    password = SYSTEM_PASSWORD

    if not reg_no:
        return jsonify({"error": "regNo is required"}), 400

    headers = {
        "Referer": "https://arms.sse.saveetha.com/FacultyPortal/Attendance.aspx"
    }

    try:
        try:
            session = session_manager.get_session(username, password)
        except Exception as e:
            return jsonify({"error": str(e)}), 401

        url_student = f"https://arms.sse.saveetha.com/Handler/Student.ashx?Page=StudentView&Mode=GETALLRECORDREGNOLIBS&Id={reg_no}"
        resp_student = session.get(url_student, headers=headers, timeout=15)
        if "Login.aspx" in resp_student.url or resp_student.status_code == 401:
            # Refresh session using stored credentials
            session = session_manager.refresh_session(username)
            resp_student = session.get(url_student, headers=headers, timeout=15)

        resp_student.raise_for_status()

        try:
            student_data = resp_student.json()
        except ValueError:
            # If ARMS returns HTML or empty response instead of JSON
            return jsonify({"error": "Failed to retrieve valid data from ARMS server. The system might be unavailable or credentials expired."}), 500

        if not student_data.get("Table") or len(student_data["Table"]) == 0:
            return jsonify({"error": "No student found with this Registration Number."}), 404

        student_id = student_data["Table"][0]["StudentId"]

        url_subjects = f"https://arms.sse.saveetha.com/Handler/Administration.ashx?Page=PRINCGETENROLLCOURSE&Mode=GETENROLLCOURSE&Id={student_id}"
        resp_subjects = session.get(url_subjects, headers=headers, timeout=15)
        if "Login.aspx" in resp_subjects.url or resp_subjects.status_code == 401:
            session = session_manager.refresh_session(username)
            resp_subjects = session.get(url_subjects, headers=headers, timeout=15)

        resp_subjects.raise_for_status()

        try:
            subjects = resp_subjects.json()
            return jsonify({"success": True, "data": subjects, "studentId": student_id})
        except ValueError:
            return jsonify({"success": True, "data": resp_subjects.text})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Request failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5003)
