import os
import pickle
import time
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes needed to read activity (steps) and body (heart rate)
SCOPES = [
    'https://www.googleapis.com/auth/fitness.activity.read',
    'https://www.googleapis.com/auth/fitness.body.read'
]

def get_fit_service():
    """Authenticates and returns the Google Fit service object."""
    creds = None
    
    # The file token.pickle stores the user's access and refresh tokens
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as refresh_err:
                # Token has been expired or revoked (invalid_grant).
                # Delete the stale token so the user can re-authenticate next time.
                print(f"Google Fit token refresh failed (token expired/revoked): {refresh_err}")
                if os.path.exists('token.pickle'):
                    os.remove('token.pickle')
                # Fall back to mock data — return None gracefully
                return None
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"Error authenticating Google Fit: {e}")
                return None
                
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('fitness', 'v1', credentials=creds)
        return service
    except Exception as e:
        print(f"Error building Fit service: {e}")
        return None

def fetch_daily_steps(service, days=7):
    """Fetches step count for the last n days."""
    if not service:
        return []
        
    now = datetime.now()
    end_time = int(time.mktime(now.timetuple())) * 1000000000
    start_time = int(time.mktime((now - timedelta(days=days)).timetuple())) * 1000000000

    dataset = f"{start_time}-{end_time}"
    
    try:
        # Data source for estimated steps
        response = service.users().dataSources().datasets().get(
            userId='me',
            dataSourceId='derived:com.google.step_count.delta:com.google.android.gms:estimated_steps',
            datasetId=dataset
        ).execute()

        steps_data = []
        # Group by day roughly (simplified)
        # Google Fit REST API is complex for aggregation, but for simplicity we fetch raw points 
        # or we can use the aggregate endpoint. Aggregate endpoint is better.
        
        body = {
            "aggregateBy": [{
                "dataTypeName": "com.google.step_count.delta",
                "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:estimated_steps"
            }],
            "bucketByTime": { "durationMillis": 86400000 },
            "startTimeMillis": start_time // 1000000,
            "endTimeMillis": end_time // 1000000
        }
        
        agg_response = service.users().dataset().aggregate(userId='me', body=body).execute()
        
        for bucket in agg_response.get('bucket', []):
            dataset = bucket.get('dataset', [])
            if dataset and dataset[0].get('point'):
                val = dataset[0]['point'][0]['value'][0].get('intVal', 0)
                steps_data.append(val)
            else:
                steps_data.append(0)
                
        return steps_data[-days:] # return last N days
        
    except Exception as e:
        print(f"Error fetching steps: {e}")
        return []

def fetch_daily_heart_rate(service, days=7):
    """Fetches average heart rate for the last n days."""
    if not service:
        return []
        
    now = datetime.now()
    end_time = int(time.mktime(now.timetuple())) * 1000
    start_time = int(time.mktime((now - timedelta(days=days)).timetuple())) * 1000

    try:
        body = {
            "aggregateBy": [{
                "dataTypeName": "com.google.heart_rate.bpm",
                "dataSourceId": "derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm"
            }],
            "bucketByTime": { "durationMillis": 86400000 },
            "startTimeMillis": start_time,
            "endTimeMillis": end_time
        }
        
        agg_response = service.users().dataset().aggregate(userId='me', body=body).execute()
        
        hr_data = []
        for bucket in agg_response.get('bucket', []):
            dataset = bucket.get('dataset', [])
            if dataset and dataset[0].get('point'):
                # index 0: average, index 1: max, index 2: min (depends on aggregate return)
                # usually fpVal for average
                val = dataset[0]['point'][0]['value'][0].get('fpVal', 0)
                hr_data.append(int(val))
            else:
                hr_data.append(75) # default fallback if no HR data for the day
                
        return hr_data[-days:]
        
    except Exception as e:
        print(f"Error fetching HR: {e}")
        return []
