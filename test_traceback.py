from app import app
import io

def test():
    app.config['TESTING'] = True
    client = app.test_client()

    with client.session_transaction() as sess:
        sess['user_id'] = 1

    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    data = {'pdf': (io.BytesIO(pdf_content), 'valid.pdf')}

    try:
        response = client.post('/user/upload', data=data, content_type='multipart/form-data')
        print("STATUS:", response.status_code)
        print("RESPONSE:", response.data.decode('utf-8'))
    except Exception as e:
        print("EXCEPTION RAISED:")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test()
