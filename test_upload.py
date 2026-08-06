from app import app
import io

def test_upload():
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as sess:
        sess['user_id'] = 1

    data = {
        'pdf': (io.BytesIO(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\n"), 'test.pdf')
    }

    response = client.post('/user/upload', data=data, content_type='multipart/form-data')
    print("Status:", response.status_code)
    print("Data:", response.data)

if __name__ == "__main__":
    test_upload()
