import os
from app import app, db, User
import unittest

def create_admin_user():
    with app.app_context():
        admin = User.get_admin()
        if not admin:
            admin = User(username='admin')
            admin.set_password('001234')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created successfully.")
        else:
            print("Admin user already exists.")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    
    create_admin_user()
    
    # Run the unit tests
    test_suite = unittest.TestLoader().discover('.')
    test_runner = unittest.TextTestRunner(verbosity=1)
    test_result = test_runner.run(test_suite)
    
    # Print test results
    if test_result.wasSuccessful():
        print("All tests passed.")
    else:
        print("Some tests failed. Please review the test output above.")
    
    # Start the Flask application regardless of test results
    print("Starting the Flask application...")
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
