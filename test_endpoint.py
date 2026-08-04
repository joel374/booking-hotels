from app import app
from db import get_db_connection

app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 1  # Assuming user 1 is admin
        sess['role'] = 'admin'
        
    response = client.post('/admin/hotel/delete/1', follow_redirects=True)
    print("Status code:", response.status_code)
    if response.status_code == 200:
        if b"Terdapat masalah pada sistem" in response.data:
            print("Crashed! Redirected to index with global error message.")
        elif b"Access denied" in response.data:
            print("Admin required failed.")
        else:
            print("Success, didn't redirect to index.")
    else:
        print("Failed with status:", response.status_code)
