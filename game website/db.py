import psycopg2
def connect():
    try:
        conn = psycopg2.connect(
            host="aws-1-eu-west-3.pooler.supabase.com", 
            database="postgres",                      
            user="postgres.djkkiehllzhmawwstqcu",        
            password="mouatezGustave#18",           
            port="6543"                               
        )
        return conn
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        return None
