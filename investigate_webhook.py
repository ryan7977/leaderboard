import requests
import json
from datetime import datetime
import pytz
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def fetch_and_analyze_webhook_data():
    url = 'https://public-webhook-receiver-juy917.replit.app/get_webhooks'
    try:
        logger.debug("Fetching webhook data...")
        response = requests.get(url)
        data = response.json()
        
        joseph_wright_data = []
        case_27594_found = False
        
        for entry in data:
            webhook_data = entry.get('data', {})
            if webhook_data.get('SetOfficerName') == 'Joseph Wright':
                timestamp = datetime.strptime(entry['timestamp'], "%Y-%m-%dT%H:%M:%S.%f%z")
                pacific_time = timestamp.astimezone(pytz.timezone('America/Los_Angeles'))
                
                # Extract case ID if present
                case_id = webhook_data.get('CaseID')
                if case_id == '27594':
                    case_27594_found = True
                    logger.debug(f"Found Case ID 27594 for Joseph Wright")
                
                entry_data = {
                    'timestamp': pacific_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
                    'lead_sales': webhook_data.get('Leadsales', 'no'),
                    'payment_amount': webhook_data.get('Paymentamount', '0'),
                    'lead_source': webhook_data.get('Leadsource', ''),
                    'opener_name': webhook_data.get('OpenerName', ''),
                    'case_id': case_id,
                    'raw_data': webhook_data  # Store complete raw data for debugging
                }
                
                joseph_wright_data.append(entry_data)
        
        print("\nJoseph Wright's Webhook Data Analysis:")
        print(f"Total entries found: {len(joseph_wright_data)}")
        
        if not case_27594_found:
            print("\nWARNING: Case ID 27594 was not found in the webhook data")
            
        print("\nDetailed entries:")
        for entry in joseph_wright_data:
            print("\nTimestamp:", entry['timestamp'])
            print("Case ID:", entry.get('case_id', 'Not specified'))
            print("Lead Sales:", entry['lead_sales'])
            print("Payment Amount:", entry['payment_amount'])
            print("Lead Source:", entry['lead_source'])
            print("Opener Name:", entry['opener_name'])
            
            # Additional debug information for case 27594
            if entry.get('case_id') == '27594':
                print("\nDEBUG INFO FOR CASE 27594:")
                print("Raw webhook data:")
                print(json.dumps(entry['raw_data'], indent=2))
            print("-" * 50)

    except Exception as e:
        logger.error(f"Error analyzing webhook data: {str(e)}")
        raise

if __name__ == "__main__":
    fetch_and_analyze_webhook_data()
