import unittest
from datetime import datetime, timedelta
from app import app, process_daily_enrollments

class TestDailyEnrollments(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_process_daily_enrollments(self):
        # Mock webhook data
        mock_data = [
            {
                'timestamp': (datetime.now() - timedelta(days=1)).isoformat(),
                'data': {'Leadsales': 'yes'}
            },
            {
                'timestamp': (datetime.now() - timedelta(days=2)).isoformat(),
                'data': {'Leadsales': 'yes'}
            },
            {
                'timestamp': (datetime.now() - timedelta(days=2)).isoformat(),
                'data': {'Leadsales': 'no'}
            }
        ]

        result = process_daily_enrollments(mock_data)

        # Check if the result is a list of dictionaries
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(item, dict) for item in result))

        # Check if each dictionary has 'date' and 'count' keys
        for item in result:
            self.assertIn('date', item)
            self.assertIn('count', item)

        # Check if the counts are correct
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")

        yesterday_count = next((item['count'] for item in result if item['date'] == yesterday), None)
        two_days_ago_count = next((item['count'] for item in result if item['date'] == two_days_ago), None)

        self.assertEqual(yesterday_count, 1)
        self.assertEqual(two_days_ago_count, 1)

    def test_daily_enrollments_api(self):
        response = self.app.get('/api/daily-enrollments')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIsInstance(data, list)
        self.assertTrue(all(isinstance(item, dict) for item in data))
        for item in data:
            self.assertIn('date', item)
            self.assertIn('count', item)

if __name__ == '__main__':
    unittest.main()
