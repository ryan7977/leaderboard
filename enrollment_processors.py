from datetime import datetime, timedelta
import pytz
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def process_daily_enrollments(data):
    """Process daily enrollments data from webhook responses."""
    pacific_tz = pytz.timezone('America/Los_Angeles')
    current_date = datetime.now(pacific_tz).date()
    daily_enrollments = {}

    for i in range(14):
        day = current_date - timedelta(days=i)
        if day.weekday() < 5:  # Only include weekdays
            daily_enrollments[(day + timedelta(days=1)).strftime("%Y-%m-%d")] = 0
        if len(daily_enrollments) == 10:
            break

    for entry in data:
        try:
            timestamp_str = entry['timestamp']
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            timestamp = datetime.fromisoformat(timestamp_str).astimezone(pacific_tz)
            date_key = (timestamp.date() + timedelta(days=1)).strftime("%Y-%m-%d")
            
            if date_key in daily_enrollments:
                lead_sales = entry['data'].get('Leadsales', 'no')
                if lead_sales.lower() == 'yes':
                    daily_enrollments[date_key] += 1
        except Exception as e:
            logger.error(f"Error processing webhook data entry for daily enrollments: {str(e)}")

    sorted_data = [{"date": date, "count": count} for date, count in daily_enrollments.items()]
    sorted_data.sort(key=lambda x: x['date'], reverse=True)
    return sorted_data[:10]

def process_leadsource_data(data):
    """Process lead source data from webhook responses."""
    current_month = datetime.now(pytz.timezone('America/Los_Angeles')).month
    leadsource_sales = {}

    for entry in data:
        try:
            timestamp = datetime.strptime(entry['timestamp'], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(pytz.timezone('America/Los_Angeles'))
            if timestamp.month == current_month:
                lead_sales = entry['data'].get('Leadsales', 'no')
                lead_source = entry['data'].get('Leadsource', '')

                if lead_sales.lower() == 'yes' and lead_source:
                    if lead_source not in leadsource_sales:
                        leadsource_sales[lead_source] = 0
                    leadsource_sales[lead_source] += 1
        except Exception as e:
            logger.error(f"Error processing webhook data entry for lead source: {str(e)}")

    return leadsource_sales

def process_admin_monthly_revenue(data):
    """Process webhook data for monthly revenue in admin panel."""
    current_month = datetime.now(pytz.timezone('America/Los_Angeles')).month
    monthly_sales = {}

    for entry in data:
        try:
            timestamp = datetime.strptime(entry['timestamp'], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(pytz.timezone('America/Los_Angeles'))
            if timestamp.month == current_month:
                officer_name = entry['data'].get('SetOfficerName', '')
                lead_sales = entry['data'].get('Leadsales', 'no')
                payment_amount = entry['data'].get('Paymentamount', '0')

                if officer_name not in monthly_sales:
                    monthly_sales[officer_name] = {
                        'name': officer_name,
                        'value': 0.0,
                        'demos': 0
                    }

                if lead_sales.lower() == 'yes':
                    monthly_sales[officer_name]['demos'] += 1

                if payment_amount:
                    try:
                        amount = float(payment_amount.strip('$').replace(',', ''))
                        monthly_sales[officer_name]['value'] += amount
                    except ValueError:
                        logger.warning(f"Invalid payment amount: {payment_amount}")
        except Exception as e:
            logger.error(f"Error processing webhook data entry for monthly sales: {str(e)}")

    return list(monthly_sales.values())

def process_monthly_revenue_enrollments(data):
    """Process webhook data for monthly revenue with initial payments data."""
    current_month = datetime.now(pytz.timezone('America/Los_Angeles')).month
    monthly_sales = {}

    for entry in data:
        try:
            timestamp = datetime.strptime(entry['timestamp'], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(pytz.timezone('America/Los_Angeles'))
            if timestamp.month == current_month:
                officer_name = entry['data'].get('SetOfficerName', '')
                payment_amount = entry['data'].get('Paymentamount', '0')

                if officer_name not in monthly_sales:
                    monthly_sales[officer_name] = {
                        'name': officer_name,
                        'value': 0.0,
                        'demos': 0
                    }

                if payment_amount:
                    try:
                        amount = float(payment_amount.strip('$').replace(',', ''))
                        monthly_sales[officer_name]['value'] += amount
                    except ValueError:
                        logger.warning(f"Invalid payment amount: {payment_amount}")
        except Exception as e:
            logger.error(f"Error processing webhook data entry for monthly sales: {str(e)}")

    # Get initial payments data and update demos count
    payments_data = process_initial_payments(data)
    for officer in monthly_sales.values():
        if officer['name'] in payments_data:
            officer['demos'] = payments_data[officer['name']]['count']

    return list(monthly_sales.values())

def process_initial_payments(data):
    """Process webhook data for initial payments tracking."""
    pacific_tz = pytz.timezone('America/Los_Angeles')
    current_month = datetime.now(pacific_tz).month
    payments = {}
    
    for entry in data:
        try:
            webhook_data = entry['data']
            
            # Skip if not an initial payment
            if webhook_data.get('InitialPayment', 'no').lower() != 'yes':
                continue
                
            # Skip if not in current month
            timestamp = datetime.strptime(entry['timestamp'], "%Y-%m-%dT%H:%M:%S.%f%z")
            if timestamp.month != current_month:
                continue
                
            # Extract required fields
            officer_name = webhook_data.get('SetOfficerName')
            case_id = webhook_data.get('CaseID')
            
            # Skip if missing required fields
            if not all([officer_name, case_id]):
                continue
                
            # Initialize officer data if needed
            if officer_name not in payments:
                payments[officer_name] = {
                    'count': 0,
                    'cases': set()
                }
                
            # Skip duplicate case IDs
            if case_id in payments[officer_name]['cases']:
                continue
                
            # Track the payment
            payments[officer_name]['count'] += 1
            payments[officer_name]['cases'].add(case_id)
                
        except Exception as e:
            logger.error(f"Error processing payment: {str(e)}")
            continue
            
    return payments

def process_enrollments_per_opener(data):
    """Process webhook data for enrollments per opener section."""
    pacific_tz = pytz.timezone('America/Los_Angeles')
    current_month = datetime.now(pacific_tz).month
    opener_enrollments = {}
    
    for entry in data:
        try:
            webhook_data = entry['data']
            timestamp = datetime.strptime(entry['timestamp'], "%Y-%m-%dT%H:%M:%S.%f%z").astimezone(pacific_tz)
            
            # Skip if not in current month
            if timestamp.month != current_month:
                continue
                
            # Skip if not a lead sale
            if webhook_data.get('Leadsales', 'no').lower() != 'yes':
                continue
                
            # Get opener name
            opener_name = webhook_data.get('OpenerName', '')
            if not opener_name:
                continue
                
            # Initialize opener data if needed
            if opener_name not in opener_enrollments:
                opener_enrollments[opener_name] = 0
                
            # Count the enrollment
            opener_enrollments[opener_name] += 1
                
        except Exception as e:
            logger.error(f"Error processing opener enrollment: {str(e)}")
            continue
    
    # Convert to sorted list of tuples (opener_name, count)
    sorted_opener_data = sorted(opener_enrollments.items(), key=lambda x: x[1], reverse=True)
    return sorted_opener_data
